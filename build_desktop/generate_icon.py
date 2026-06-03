"""
Gera o ícone SFSC em múltiplos tamanhos e exporta como .ico multi-resolução.
Visual: fundo azul Orzio com letra "S" branca bold e detalhe coral (viga).
Executar: python build_desktop/generate_icon.py
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent

# Cores Orzio
BLUE   = (20,  71, 230)    # #1447E6
CYAN   = (34, 211, 238)    # #22D3EE
CORAL  = (255, 107, 91)    # #FF6B5B
WHITE  = (255, 255, 255)
DARK   = (15,  23,  42)    # #0F172A

SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Fundo azul com cantos arredondados ──
    r = max(3, size // 8)
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=r, fill=BLUE)

    # ── Banda cyan no topo (representa laje / estrutura) ──
    band_h = max(2, size // 10)
    draw.rounded_rectangle([(0, 0), (size - 1, band_h + r)], radius=r, fill=CYAN)
    draw.rectangle([(0, r), (size - 1, band_h + r)], fill=CYAN)

    # ── Dois pendurais corais (varões verticais) ──
    rod_w = max(1, size // 18)
    rod_top = band_h
    rod_bot = int(size * 0.68)
    x1 = size // 4
    x2 = (3 * size) // 4
    draw.rectangle([(x1 - rod_w, rod_top), (x1 + rod_w, rod_bot)], fill=CORAL)
    draw.rectangle([(x2 - rod_w, rod_top), (x2 + rod_w, rod_bot)], fill=CORAL)

    # ── Viga horizontal azul escura (equipamento / duto) ──
    beam_y1 = rod_bot
    beam_y2 = int(size * 0.84)
    margin = max(2, size // 12)
    draw.rounded_rectangle(
        [(margin, beam_y1), (size - margin - 1, beam_y2)],
        radius=max(1, size // 20),
        fill=WHITE,
    )

    # ── Letra "S" sobre a viga para identificação SFSC ──
    if size >= 32:
        font_size = max(8, int(size * 0.30))
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        text = "S"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (size - tw) // 2
        ty = beam_y1 + (beam_y2 - beam_y1 - th) // 2 - bbox[1]
        draw.text((tx, ty), text, fill=BLUE, font=font)

    return img


def main():
    frames = [render_icon(s) for s in SIZES]

    # Guardar ICO multi-resolução
    ico_path = ROOT / "build_desktop" / "sfsc.ico"
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[1:],
    )
    print(f"ICO gerado: {ico_path}")

    # Guardar PNG 256 para referência
    png_path = ROOT / "build_desktop" / "sfsc_256.png"
    frames[-1].save(png_path, format="PNG")
    print(f"PNG 256px: {png_path}")


if __name__ == "__main__":
    main()
