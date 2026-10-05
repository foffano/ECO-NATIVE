import re
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import Asset, Listing, Product, Project, StoreProfile
from backend.app.db.store import store
from backend.app.services.shopee_template import (
    ShopeeTemplateError,
    fill_template,
    parse_dimensions,
    validate_template,
)

KEYS = [
    "ps_category|0|0", "ps_product_name|1|0", "ps_product_description|1|0", "ps_sku_parent_short|0|0",
    "et_title_variation_integration_no|0|0", "et_title_variation_1|0|0", "et_title_option_for_variation_1|0|0",
    "et_title_image_per_variation|0|3", "ps_price|1|1", "ps_stock|0|1", "ps_sku_short|0|0",
    "ps_item_cover_image|0|3", "ps_item_image_1|0|3", "ps_weight|1|1", "ps_length|0|1", "ps_width|0|1",
    "ps_height|0|1", "ps_invoice_ncm|0|0",
]


def column(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def make_template(path, *, extra_rows=0):
    """A minimal workbook shaped like Shopee's: a guide sheet, then the product
    sheet with six header rows, shared strings, column styles and validations."""
    strings = KEYS + ["Orientação"]
    shared = "".join(f"<si><t>{text}</t></si>" for text in strings)
    header = "".join(f'<c r="{column(i + 1)}1" t="s"><v>{i}</v></c>' for i in range(len(KEYS)))
    rows = f'<row r="1" hidden="true">{header}</row>' + "".join(f'<row r="{n}"><c r="A{n}" t="s"><v>{len(KEYS)}</v></c></row>' for n in range(2, 7 + extra_rows))
    product_sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1"></dimension>'
        '<cols><col min="2" max="2" style="6" width="20"></col></cols>'
        f"<sheetData>{rows}</sheetData>"
        '<sheetProtection sheet="true"></sheetProtection>'
        '<dataValidations count="1"><dataValidation type="list" sqref="R7:R1007"><formula1>"Sim,Não"</formula1></dataValidation></dataValidations>'
        "</worksheet>"
    )
    guide = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>'
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        '<sheet name="Orientação" sheetId="1" r:id="rId1"></sheet><sheet name="Modelo" sheetId="2" r:id="rId5"></sheet>'
        "</sheets></workbook>"
    )
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"></Relationship>'
        '<Relationship Id="rId5" Target="worksheets/sheet2.xml" Type="worksheet"></Relationship>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared}</sst>')
        archive.writestr("xl/worksheets/sheet1.xml", guide)
        archive.writestr("xl/worksheets/sheet2.xml", product_sheet)
    return path


def cells(path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
    result = {}
    for ref, inner in re.findall(r'<c r="([A-Z]+(?:[7-9]|\d\d+))"[^>]*>(.*?)</c>', xml, re.S):
        text = re.search(r"<t[^>]*>(.*?)</t>", inner, re.S) or re.search(r"<v>(.*?)</v>", inner)
        result[ref] = text.group(1)
    return result


def test_fill_appends_rows_and_keeps_every_other_part(tmp_path):
    template = make_template(tmp_path / "template.xlsx")
    output = tmp_path / "out.xlsx"
    rows = [{
        "Categoria": "",
        "Nome do Produto": "Suporte <Fone> & Cia",
        "Descrição do Produto": "Linha 1\nLinha 2\x01",
        "Preço": "39,90",
        "Estoque": "10",
        "Peso": "0.15",
        "Comprimento": "20",
        "Número de Integração de Variação": "1",
    }]

    fill_template(template, rows, output)

    with zipfile.ZipFile(template) as before, zipfile.ZipFile(output) as after:
        assert before.namelist() == after.namelist()
        for name in before.namelist():
            if name != "xl/worksheets/sheet2.xml":
                assert before.read(name) == after.read(name), name
        old_sheet = before.read("xl/worksheets/sheet2.xml").decode()
        new_sheet = after.read("xl/worksheets/sheet2.xml").decode()
    # Only new rows were inserted before </sheetData>.
    start = old_sheet.index("</sheetData>")
    assert new_sheet[:start] == old_sheet[:start]
    assert new_sheet.endswith(old_sheet[start:])

    values = cells(output)
    assert values["B7"] == "Suporte &lt;Fone&gt; &amp; Cia"
    assert values["C7"] == "Linha 1\nLinha 2"
    assert values["I7"] == "39.9"  # numeric cell, dot decimal
    assert values["N7"] == "0.15"
    assert values["O7"] == "20"
    assert "A7" not in values  # category left for the seller to choose
    assert 's="6"' in re.search(r'<c r="B7"[^>]*>', new_sheet).group(0)  # column style kept


def test_template_with_products_or_without_product_sheet_is_rejected(tmp_path):
    with pytest.raises(ShopeeTemplateError, match="já tem produtos"):
        validate_template(make_template(tmp_path / "used.xlsx", extra_rows=1))
    not_xlsx = tmp_path / "x.xlsx"
    not_xlsx.write_text("não é zip")
    with pytest.raises(ShopeeTemplateError, match="xlsx válida"):
        validate_template(not_xlsx)


def test_too_many_rows_are_refused(tmp_path):
    template = make_template(tmp_path / "template.xlsx")
    with pytest.raises(ShopeeTemplateError, match="até 1000"):
        fill_template(template, [{"Nome do Produto": "x"}] * 1001, tmp_path / "out.xlsx")


def test_parse_dimensions():
    assert parse_dimensions("L:20 W:10 H:8") == (20, 10, 8)
    assert parse_dimensions("L:9 W:9 H:9 (Dimensions estimated in cm)") == (9, 9, 9)
    assert parse_dimensions("12x8,5x4") == (12, 8.5, 4)
    assert parse_dimensions("") is None


def client_for(shop):
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session
    create_initial_users(("admin", "password123"), [("shop", "password123", shop.id)])
    client = TestClient(app)
    client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop")))
    return client


def test_upload_template_and_export_selected_products(tmp_path):
    shop = store.upsert_store_profile(StoreProfile(name="Eco Loja"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    product = store.upsert_product(Product(
        project_id=project.id,
        name="Organizador",
        listing=Listing(title="Organizador de Mesa", description="Descrição completa", category="Casa > Organização",
                        price="24.90", stock=5, weight="0.12", parcel_size="L:16 W:12 H:4"),
        assets=[Asset(product_id="x", kind="cover_image", path="", public_url="https://cdn.example/capa.jpg")],
        metadata={"sku": "ECO-001"},
    ))
    client = client_for(shop)

    assert client.get("/api/exports/shopee-template").json() == {"configured": False}
    payload = {"project_id": project.id, "product_ids": [product.id]}
    assert client.post("/api/exports/shopee-xlsx", json=payload).status_code == 409

    template = make_template(tmp_path / "template.xlsx")
    uploaded = client.post("/api/exports/shopee-template", files={"file": ("modelo.xlsx", template.read_bytes())})
    assert uploaded.json()["configured"] is True
    bad = client.post("/api/exports/shopee-template", files={"file": ("modelo.xlsx", b"nada")})
    assert bad.status_code == 400

    response = client.post("/api/exports/shopee-xlsx", json=payload)
    assert response.status_code == 200
    assert response.headers["x-eco-export-count"] == "1"
    output = tmp_path / "exportado.xlsx"
    output.write_bytes(response.content)
    values = cells(output)
    assert values["B7"] == "Organizador de Mesa"
    assert values["D7"] == "ECO-001"
    assert values["I7"] == "24.9"
    assert values["L7"] == "https://cdn.example/capa.jpg"
    assert (values["O7"], values["P7"], values["Q7"]) == ("16", "12", "4")
    assert store.snapshot().products[0].status == "exported"

    other = {"project_id": project.id, "product_ids": ["de-outra-loja"]}
    assert client.post("/api/exports/shopee-xlsx", json=other).status_code == 400
