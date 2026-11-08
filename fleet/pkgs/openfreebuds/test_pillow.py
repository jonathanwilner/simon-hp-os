"""Exercise the image operations used by OpenFreebuds with the pinned Pillow."""
from PIL import Image, ImageQt
from PyQt6.QtWidgets import QApplication
from openfreebuds_qt.utils.draw import image_spawn_bg_mask, image_combine_mask

app = QApplication([])
mask = image_spawn_bg_mask(0.5, (16, 16))
foreground = Image.new("RGBA", mask.size, "red")
background = Image.new("RGBA", mask.size, "blue")
image = image_combine_mask(mask, foreground, background)
assert image.getpixel((8, 0)) == (0, 0, 255, 255)
assert image.getpixel((8, 15)) == (255, 0, 0, 255)
image.thumbnail((8, 8))
assert not ImageQt.toqpixmap(image).isNull()
print("OpenFreebuds Pillow mask, composition, resize and Qt conversion passed")
