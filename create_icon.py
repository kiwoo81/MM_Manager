"""MM 관리 시스템 아이콘 생성 스크립트."""
import os
from PIL import Image, ImageDraw


def create_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size

    # 배경 원형 (짙은 청색)
    margin = max(1, int(s * 0.04))
    draw.ellipse([margin, margin, s - margin, s - margin],
                 fill=(21, 101, 192, 255))

    # 내부 밝은 원 (하이라이트)
    hl = max(2, int(s * 0.08))
    draw.ellipse([hl, hl, s - hl, s - hl],
                 fill=(25, 118, 210, 255))

    # ── 사람 아이콘 (위쪽 중앙) ──────────────────────────────────────────
    cx = s / 2
    head_r = max(1, s * 0.10)
    head_cy = s * 0.30
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=(255, 255, 255, 255)
    )
    body_w = s * 0.22
    body_top = head_cy + head_r + max(1, s * 0.02)
    body_bot_center = head_cy + head_r + s * 0.18 + body_w
    draw.ellipse(
        [cx - body_w, body_top, cx + body_w, body_bot_center],
        fill=(255, 255, 255, 200)
    )

    # ── 막대 그래프 (아래쪽) ─────────────────────────────────────────────
    if s >= 32:
        bar_y_bot = s * 0.88
        bar_w = s * 0.09
        bar_gap = s * 0.04
        bars = [0.55, 0.75, 0.45, 0.90]
        total_w = len(bars) * bar_w + (len(bars) - 1) * bar_gap
        bar_x0 = cx - total_w / 2
        bar_max_h = s * 0.30

        colors = [
            (144, 202, 249, 230),
            (100, 181, 246, 230),
            (66,  165, 245, 230),
            (255, 255, 255, 230),
        ]
        for i, (ratio, color) in enumerate(zip(bars, colors)):
            bx = bar_x0 + i * (bar_w + bar_gap)
            bh = bar_max_h * ratio
            r = max(1, int(bar_w * 0.25))
            draw.rounded_rectangle(
                [bx, bar_y_bot - bh, bx + bar_w, bar_y_bot],
                radius=r, fill=color
            )

    return img


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)

    # Pillow 네이티브 ICO 저장 (BMP 기반, Windows 탐색기 호환)
    # 256x256 기준 이미지에서 각 사이즈로 리샘플링하여 저장
    base = create_icon(256)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    base.save(
        "assets/icon.ico",
        format="ICO",
        sizes=sizes
    )
    print("아이콘 생성 완료: assets/icon.ico")
