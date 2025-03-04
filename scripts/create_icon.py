from PIL import Image, ImageDraw, ImageFont
import os
import sys

def create_icon():
    """创建应用图标"""
    try:
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

        text = "T"  # 使用英文字母代替中文
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

        # 使用ASCII字符输出
        print("Icon file created: app.ico")
        return True
    except Exception as e:
        print("Error creating icon:", str(e), file=sys.stderr)
        return False

if __name__ == "__main__":
    # 设置stdout编码为utf-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    success = create_icon()
    sys.exit(0 if success else 1)