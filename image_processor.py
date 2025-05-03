import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageChops
import PIL.ImageOps
from PIL import Image
import os
def trimImage(im):
    bg = PIL.Image.new(im.mode, im.size, (255,255,255))
    diff = PIL.ImageChops.difference(im, bg)
    diff = PIL.ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        return im.crop((bbox[0],bbox[1],bbox[2],bbox[3]+10))  # don't cut off the end of the image

def create_text(text, printer_width, font_name="Lucon.ttf", font_size=12):
    img = PIL.Image.new('RGB', (printer_width, 5000), color = (255, 255, 255))
    font = PIL.ImageFont.truetype(font_name, font_size)
    
    d = PIL.ImageDraw.Draw(img)
    lines = []
    for line in text.splitlines():
        lines.append(get_wrapped_text(line, font, printer_width))
    lines = "\n".join(lines)
    d.text((0,0), lines, fill=(0,0,0), font=font)
    return trimImage(img)

def get_wrapped_text(text: str, printer_width: int, font: PIL.ImageFont.ImageFont):
    lines = ['']
    for word in text.split():
        line = f'{lines[-1]} {word}'.strip()
        if font.getlength(line) <= printer_width:
            lines[-1] = line
        else:
            lines.append(word)
    return '\n'.join(lines)

def process_image_for_printing(im, printer_width):
    # Handle transparent PNGs by converting to white background
    if im.mode == 'RGBA':
        background = PIL.Image.new('RGB', im.size, (255, 255, 255))
        background.paste(im, mask=im.split()[-1])
        im = background
    
    if im.width > printer_width:
        # image is wider than printer resolution; scale it down proportionately
        height = int(im.height * (printer_width / im.width))
        im = im.resize((printer_width, height))
        
    if im.width < printer_width:
        # image is narrower than printer resolution; pad it out with white pixels
        padded_image = PIL.Image.new("1", (printer_width, im.height), 1)
        padded_image.paste(im)
        im = padded_image

    # if in debug mode, save the image
    if os.getenv("DEBUG"):
        im.save("processed_image.png")
        
    return _finalize_image_for_printing(im)

def _finalize_image_for_printing(im):
    """
    Apply final processing steps to prepare image for printing.
    Includes rotation, mode conversion, width alignment, and inversion.
    """
    im = im.rotate(180)  # print it so it looks right when spewing out of the mouth
    
    # if image is not 1-bit, convert it
    if im.mode != '1':
        im = im.convert('1')
        
    # if image width is not a multiple of 8 pixels, fix that
    if im.size[0] % 8:
        im2 = Image.new('1', (im.size[0] + 8 - im.size[0] % 8, 
                        im.size[1]), 'white')
        im2.paste(im, (0, 0))
        im = im2
        
    # Invert image, via greyscale for compatibility
    # (no, I don't know why I need to do this)
    im = PIL.ImageOps.invert(im.convert('L'))
    # ... and now convert back to single bit
    im = im.convert('1')

    # if in debug mode, save the image
    if os.getenv("DEBUG"):
        im.save("finalized_image.png")

    return im 