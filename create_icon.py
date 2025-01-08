from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """创建应用图标"""
    # 创建一个 256x256 的图像
    size = (256, 256)
    image = Image.new('RGBA', size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    # 绘制圆形背景
    circle_bbox = (20, 20, 236, 236)
    draw.ellipse(circle_bbox, fill='#2196F3')

    # 添加文字
    try:
        font = ImageFont.truetype('Arial.ttf', 120)
    except:
        font = ImageFont.load_default()

    text = "税"
    # 获取文字大小
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # 计算文字位置（居中）
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2

    # 绘制文字
    draw.text((x, y), text, fill='white', font=font)

    # 保存为ICO文件
    image.save('app.ico', format='ICO', sizes=[(256, 256)])
    print("图标已创建: app.ico")

if __name__ == "__main__":
    create_icon()