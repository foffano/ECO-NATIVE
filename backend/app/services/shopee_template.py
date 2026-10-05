"""Fill the store's own Shopee mass-upload template (.xlsx).

Shopee templates are tied to the seller account (hidden template/shop ids,
the shop's brand list), so each store uploads the one it downloaded from the
Seller Centre. Filling only appends rows to the "Modelo" sheet XML: every
other part of the package is copied byte for byte, so validations, protection,
hidden sheets and styles stay exactly as Shopee generated them.
"""

import html
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Template column key (row 1, before the "|") for each field the exporter fills.
FIELD_KEYS = {
    "Nome do Produto": "ps_product_name",
    "Descrição do Produto": "ps_product_description",
    "SKU principal": "ps_sku_parent_short",
    "Número de Integração de Variação": "et_title_variation_integration_no",
    "Nome da Variação 1": "et_title_variation_1",
    "Opção para Variação 1": "et_title_option_for_variation_1",
    "Imagem por Variação": "et_title_image_per_variation",
    "Preço": "ps_price",
    "Estoque": "ps_stock",
    "SKU da Variação": "ps_sku_short",
    "Imagem de capa": "ps_item_cover_image",
    **{f"Imagem do produto {index}": f"ps_item_image_{index}" for index in range(1, 9)},
    "Peso": "ps_weight",
    "Comprimento": "ps_length",
    "Largura": "ps_width",
    "Altura": "ps_height",
}
NUMERIC_KEYS = {"ps_price", "ps_stock", "ps_weight", "ps_length", "ps_width", "ps_height"}
REQUIRED_KEYS = {"ps_product_name", "ps_product_description", "ps_price", "ps_weight"}
# Rows 1-6 are Shopee's header block; product rows start right after it and its
# data validations cover up to row 1006.
HEADER_ROWS = 6
MAX_DATA_ROWS = 1000

_INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


class ShopeeTemplateError(ValueError):
    pass


@dataclass(frozen=True)
class TemplateLayout:
    sheet_path: str
    columns: dict[str, str]  # template key -> column letters
    column_styles: dict[int, str]  # column index (1-based) -> style id
    max_row: int


def _column_index(letters: str) -> int:
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index


def _column_letters(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml = archive.read("xl/sharedStrings.xml").decode("utf-8")
    except KeyError:
        return []
    items = re.findall(r"<si>(.*?)</si>", xml, re.S)
    return [html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", item, re.S))) for item in items]


def _sheet_paths(archive: zipfile.ZipFile) -> list[str]:
    workbook = archive.read("xl/workbook.xml").decode("utf-8")
    rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = {}
    for rel in re.findall(r"<Relationship\b[^>]*>", rels):
        rel_id = re.search(r'\bId="([^"]+)"', rel)
        target = re.search(r'\bTarget="([^"]+)"', rel)
        if rel_id and target:
            targets[rel_id.group(1)] = target.group(1)
    paths = []
    for sheet in re.findall(r"<sheet\b[^>]*>", workbook):
        rel_id = re.search(r'r:id="([^"]+)"', sheet)
        target = targets.get(rel_id.group(1)) if rel_id else None
        if target:
            path = target.lstrip("/") if target.startswith("/") else str(PurePosixPath("xl") / target)
            paths.append(path)
    return paths


def _cell_text(cell_attrs: str, inner: str, strings: list[str]) -> str:
    value = re.search(r"<v>(.*?)</v>", inner, re.S)
    if 't="s"' in cell_attrs and value:
        return strings[int(value.group(1))]
    inline = re.findall(r"<t[^>]*>(.*?)</t>", inner, re.S)
    if inline:
        return html.unescape("".join(inline))
    return html.unescape(value.group(1)) if value else ""


def read_layout(path: Path) -> TemplateLayout:
    """Find the product sheet (the one whose first row holds the ps_* keys)."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ShopeeTemplateError("O arquivo não é uma planilha .xlsx válida") from error
    with archive:
        strings = _shared_strings(archive)
        for sheet_path in _sheet_paths(archive):
            xml = archive.read(sheet_path).decode("utf-8")
            first_row = re.search(r'<row\b[^>]*\br="1"[^>]*>(.*?)</row>', xml, re.S)
            if not first_row:
                continue
            columns = {}
            for letters, attrs, inner in re.findall(r'<c r="([A-Z]+)1"([^>]*?)(?:/>|>(.*?)</c>)', first_row.group(1), re.S):
                key = _cell_text(attrs, inner or "", strings).split("|", 1)[0].strip()
                if key:
                    columns[key] = letters
            if "ps_product_name" not in columns:
                continue
            missing = REQUIRED_KEYS - columns.keys()
            if missing:
                raise ShopeeTemplateError("Template da Shopee sem colunas obrigatórias: " + ", ".join(sorted(missing)))
            column_styles = {}
            for col in re.findall(r"<col\b[^>]*>", xml):
                low, high, style = (re.search(rf'\b{name}="([^"]+)"', col) for name in ("min", "max", "style"))
                if low and high and style:
                    for index in range(int(low.group(1)), int(high.group(1)) + 1):
                        column_styles[index] = style.group(1)
            rows = [int(number) for number in re.findall(r'<row\b[^>]*\br="(\d+)"', xml)]
            return TemplateLayout(sheet_path, columns, column_styles, max(rows, default=0))
    raise ShopeeTemplateError("Não encontrei a aba de produtos do template de envio em massa da Shopee")


def validate_template(path: Path) -> TemplateLayout:
    layout = read_layout(path)
    if layout.max_row > HEADER_ROWS:
        raise ShopeeTemplateError("Este template já tem produtos preenchidos. Envie um template novo, baixado da Shopee.")
    return layout


def parse_number(value: object) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def parse_dimensions(parcel_size: str) -> tuple[float, float, float] | None:
    """'L:20 W:10 H:8' or '20x10x8' (cm) -> (length, width, height)."""
    text = parcel_size or ""
    labelled = {key.upper(): float(value.replace(",", ".")) for key, value in re.findall(r"([LWH])\s*:\s*(\d+(?:[.,]\d+)?)", text, re.I)}
    if {"L", "W", "H"} <= labelled.keys():
        return labelled["L"], labelled["W"], labelled["H"]
    plain = re.search(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)", text, re.I)
    if plain:
        return tuple(float(part.replace(",", ".")) for part in plain.groups())  # type: ignore[return-value]
    return None


def _format_number(number: float) -> str:
    return str(int(number)) if number == int(number) else repr(round(number, 4))


def _cell_xml(ref: str, value: str, key: str, style: str | None) -> str:
    style_attr = f' s="{style}"' if style else ""
    if key in NUMERIC_KEYS:
        number = parse_number(value)
        if number is not None:
            return f'<c r="{ref}"{style_attr}><v>{_format_number(number)}</v></c>'
    text = html.escape(_INVALID_XML_CHARS.sub("", value), quote=False)
    return f'<c r="{ref}"{style_attr} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _rows_xml(layout: TemplateLayout, rows: list[dict[str, str]]) -> str:
    output = []
    for offset, row in enumerate(rows):
        number = HEADER_ROWS + 1 + offset
        cells = []
        for field, value in row.items():
            key = FIELD_KEYS.get(field)
            letters = layout.columns.get(key or "")
            if not letters or value in (None, ""):
                continue
            cells.append((_column_index(letters), key, str(value)))
        cells.sort()
        xml = "".join(
            _cell_xml(f"{_column_letters(index)}{number}", value, key, layout.column_styles.get(index))
            for index, key, value in cells
        )
        output.append(f'<row r="{number}">{xml}</row>')
    return "".join(output)


def fill_template(template: Path, rows: list[dict[str, str]], output: Path) -> None:
    layout = validate_template(template)
    if len(rows) > MAX_DATA_ROWS:
        raise ShopeeTemplateError(
            f"A planilha da Shopee aceita até {MAX_DATA_ROWS} linhas e a seleção gera {len(rows)}. Exporte em partes menores."
        )
    with zipfile.ZipFile(template) as source:
        sheet = source.read(layout.sheet_path).decode("utf-8")
        if sheet.count("</sheetData>") != 1:
            raise ShopeeTemplateError("Formato inesperado na aba de produtos do template")
        filled = sheet.replace("</sheetData>", _rows_xml(layout, rows) + "</sheetData>")
        with zipfile.ZipFile(output, "w") as target:
            for info in source.infolist():
                data = filled.encode("utf-8") if info.filename == layout.sheet_path else source.read(info.filename)
                target.writestr(info, data, compress_type=info.compress_type)
