SHOPEE_LISTING_PROMPT = """
Voce e um assistente especialista em e-commerce para a Shopee Brasil.
Analise as imagens do produto fornecidas e o relato tecnico extraido do modelo 3D (se disponivel).

REGRAS ESTRITAS DE CONTEUDO:
1. NUNCA MENCIONE que o produto e impresso em 3D, feito em PLA, ou manufatura aditiva. Aja como se fosse um produto industrializado padrao. Nenhuma mencao a "camadas" ou "impressao".
2. NUNCA UTILIZE EMOJIS em nenhuma parte do texto.
3. NUNCA UTILIZE ASTERISCOS (*) para negrito ou destaque. Para destacar palavras importantes, utilize APENAS CAIXA ALTA.
4. Siga rigorosamente a estrutura de descricao solicitada.

Saida deve ser estritamente em PORTUGUES (PT-BR).

Gere um objeto JSON com a seguinte estrutura:
{
    "Product Name": "Um titulo conciso e otimizado para SEO (Max 100 caracteres)",
    "Product Description": "DEVE seguir EXATAMENTE esta estrutura:\\n\\n[TITULO CHAMATIVO EM CAIXA ALTA]\\n\\n[Paragrafo introdutorio persuasivo e profissional]\\n\\nPRINCIPAIS CARACTERISTICAS:\\n- [Caracteristica 1]\\n- [Caracteristica 2]\\n- [Caracteristica 3]\\n\\nESPECIFICACOES TECNICAS:\\n- Material: Polimero de Alta Resistencia (nunca citar PLA/3D)\\n- Dimensoes Aproximadas: [Inserir dados baseados visualmente ou deixe estimativa conservadora]\\n- Cor: [Descrever com base na imagem se possivel]\\n\\nCONTEUDO DA EMBALAGEM:\\n- 1x [Nome do Produto]\\n\\nATENCAO:\\n- [Aviso claro de que dispositivos eletronicos/cenarios nao estao inclusos]\\n\\nUse quebras de linha (\\n) para garantir essa formatacao visual.",
    "Category Name": "O nome da categoria Shopee mais apropriada (ex: 'Casa e Decoracao > Organizacao > Suportes')",
    "Price": "Sugira um preco ideal para venda no Brasil em BRL com base em utilidades parecidas da plataforma ou pelo peso inferido de plastico (apenas numero, ex: 35.90)",
    "Stock": 10,
    "Weight": "Peso estimado em kg visando frete (ex: 0.2)",
    "Parcel Size": "L:10 W:10 H:10 (Dimensions estimated in cm)"
}

Para a categoria, tente ser o mais especifico possivel dentro da arvore de categorias da Shopee Brasil.
"""

IMAGE_PROMPTS = {
    "studio_classic": "Cute kawaii style product photography of this EXACT 3D printed product, centered, 1:1 aspect ratio. Soft pastel background (pink, lavender or cream), soft diffused lighting, gentle shadows. Clean composition, sharp focus, 8k resolution, e-commerce style but cute and friendly. IMPORTANT: Preserve the exact shape, geometry, proportions, textures, and colors of the original product. Do not redesign, simplify, or modify any physical features. Do not add or remove parts. STRICT RULE: DO NOT add any brand logos or watermarks to the image.",
    "studio_angle": "Cute kawaii style product photography of this EXACT 3D printed product, captured from a 3/4 perspective angle showing its depth and side details, 1:1 aspect ratio. Soft neutral pastel background, professional studio three-point lighting, soft shadows. Clean and modern composition, sharp focus, 8k resolution, premium e-commerce style. IMPORTANT: Preserve the exact shape, geometry, proportions, textures, and colors of the original product. Do not redesign, simplify, or modify any physical features. Do not add or remove parts. STRICT RULE: DO NOT add any brand logos or watermarks to the image.",
    "studio_pedestal": "Cute kawaii style product photography of this EXACT 3D printed product, elegantly placed on a small minimalist cylinder pedestal, centered, 1:1 aspect ratio. Soft pastel gradient background, professional studio lighting with gentle highlights, soft shadows. Premium clean e-commerce presentation, sharp focus, 8k resolution. IMPORTANT: Preserve the exact shape, geometry, proportions, textures, and colors of the original product. Do not redesign, simplify, or modify any physical features. Do not add or remove parts. STRICT RULE: DO NOT add any brand logos or watermarks to the image.",
    "studio_close_up": "Close-up studio photography of this EXACT 3D printed product, showcasing its fine details and surface textures, 1:1 aspect ratio. Soft pastel background, soft diffused lighting, shallow depth of field with a clean background. Adorable and neat composition, sharp focus, 8k resolution. IMPORTANT: Preserve the exact shape, geometry, proportions, textures, and colors of the original product. Do not redesign, simplify, or modify any physical features. Do not add or remove parts. STRICT RULE: DO NOT add any brand logos or watermarks to the image.",
    "studio_ad_layout": "Cute kawaii style product photography of this EXACT 3D printed product, framed on the left side of the image, leaving clean negative space on the right side for adding text, 1:1 aspect ratio. Soft pastel background, soft diffused studio lighting, gentle shadows. Balanced composition optimized for advertisements, sharp focus, 8k resolution. IMPORTANT: Preserve the exact shape, geometry, proportions, textures, and colors of the original product. Do not redesign, simplify, or modify any physical features. Do not add or remove parts. STRICT RULE: DO NOT add any brand logos or watermarks to the image.",
    "studio_decor": "Cute kawaii style product photography of this EXACT 3D printed product, centered, 1:1 aspect ratio. Placed on a clean white surface with subtle, soft-focused pastel decorative props (like a tiny artificial plant or a small star figure) in the background. Soft pastel background, gentle studio lighting, clean composition, sharp focus, 8k resolution. IMPORTANT: Preserve the exact shape, geometry, proportions, textures, and colors of the original product. Do not redesign, simplify, or modify any physical features. Do not add or remove parts. STRICT RULE: DO NOT add any brand logos or watermarks to the image.",
}

FILAMENT_COLORS = [
    ("PLA_Yellow", "Standard Yellow PLA 3D printing filament, glossy finish"),
    ("PLA_Black", "Standard Black PLA 3D printing filament, glossy reflective finish"),
    ("PLA_GreyMetallic", "Standard Grey PLA 3D printing filament, semi-gloss finish"),
    ("PLA_TiffanyBlue", "Standard Tiffany Blue (Teal) PLA 3D printing filament, glossy finish"),
    ("PLA_Red", "Standard Red PLA 3D printing filament, glossy finish"),
    ("PLA_Green", "Standard Green PLA 3D printing filament, glossy finish"),
    ("PLA_BlueMetallic", "Standard Metallic Blue PLA 3D printing filament, semi-gloss finish"),
    ("PLA_Blue", "Standard Blue PLA 3D printing filament, semi-gloss finish"),
    ("PLA_Purple", "Standard Purple PLA 3D printing filament, glossy finish"),
    ("PLA_BabyPink", "Standard Baby Pink PLA 3D printing filament, soft glossy finish"),
    ("PLA_NeonPink", "Standard Neon Pink PLA 3D printing filament, vibrant glossy finish"),
    ("PLA_BabyBlue", "Standard Baby Blue PLA 3D printing filament, soft glossy finish"),
    ("PLA_Magenta", "Standard Magenta PLA 3D printing filament, deep pink glossy finish"),
    ("Velvet_White", "Velvet White PLA 3D printing filament, matte ceremonial white finish, non-reflective"),
]


DEFAULT_COLOR_VARIATION_PROMPT = (
    "Strictly maintain the original object's physical texture, geometry, layer lines, and surface details. "
    "Do NOT change the texture pattern. Only modify the color and surface finish (glossiness/matte) "
    "to update the material to: {color_description}. "
    "The lighting, angle, and background must remain identical to the source image. "
    "{extra_prompt}"
)


def color_variation_prompt(color_description: str, extra_prompt: str = "") -> str:
    return DEFAULT_COLOR_VARIATION_PROMPT.format(
        color_description=color_description,
        extra_prompt=extra_prompt,
    )


def render_color_variation_prompt(template: str, color_description: str, extra_prompt: str = "") -> str:
    try:
        return template.format(color_description=color_description, extra_prompt=extra_prompt)
    except Exception:
        return f"{template}\n\nTarget material/color: {color_description}\n{extra_prompt}".strip()
