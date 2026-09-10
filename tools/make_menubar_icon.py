"""Render the Corral menu bar icon (a fenced corral) as a template PNG.

Usage: venv/bin/python3 tools/make_menubar_icon.py [OUT.png] [SCALE]

Draws with AppKit so no extra dependencies are needed. The output is a
black-on-transparent template image; macOS recolors it for light/dark
menu bars. Default is 36x36 px (18 pt at 2x) written to
corral/static/menubar-icon.png.
"""
import os
import sys

import AppKit

SIZE = 18  # points


def draw(scale):
    px = int(SIZE * scale)
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, px, px, 8, 4, True, False, AppKit.NSCalibratedRGBColorSpace, 0, 0)
    ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(ctx)
    ctx.setShouldAntialias_(True)

    xf = AppKit.NSAffineTransform.transform()
    xf.scaleBy_(scale)
    xf.concat()

    AppKit.NSColor.blackColor().set()

    def Y(y):  # design coordinates are y-down; AppKit is y-up
        return SIZE - y

    def stroke(path, width):
        path.setLineWidth_(width)
        path.setLineCapStyle_(AppKit.NSRoundLineCapStyle)
        path.setLineJoinStyle_(AppKit.NSRoundLineJoinStyle)
        path.stroke()

    def line(x1, y1, x2, y2, width):
        p = AppKit.NSBezierPath.bezierPath()
        p.moveToPoint_((x1, Y(y1)))
        p.lineToPoint_((x2, Y(y2)))
        stroke(p, width)

    def poly(points, width, closed=True):
        p = AppKit.NSBezierPath.bezierPath()
        p.moveToPoint_((points[0][0], Y(points[0][1])))
        for x, y in points[1:]:
            p.lineToPoint_((x, Y(y)))
        if closed:
            p.closePath()
        stroke(p, width)

    # A square pen seen from above at an angle (isometric): four corner
    # posts joined by two rails per side. The rails form two stacked
    # diamonds; the posts poke above and below them.
    cx, cy = 9.0, 6.4        # centre of the upper rail diamond
    hw, hh = 7.4, 2.6        # diamond half-width / half-height
    drop = 5.2               # vertical gap between the two rails (>= 2*hh so they never cross)
    post_w, rail_w = 2.1, 1.3
    overhang = 1.4

    def diamond(y):
        return [(cx, y - hh), (cx + hw, y), (cx, y + hh), (cx - hw, y)]

    poly(diamond(cy), rail_w)
    poly(diamond(cy + drop), rail_w)
    for x, y in diamond(cy):
        line(x, y - overhang, x, y + drop + overhang, post_w)

    AppKit.NSGraphicsContext.restoreGraphicsState()
    return rep


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "corral", "static", "menubar-icon.png")
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    rep = draw(scale)
    data = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None)
    data.writeToFile_atomically_(out, True)
    print(f"wrote {out} ({rep.pixelsWide()}x{rep.pixelsHigh()})")


if __name__ == "__main__":
    main()
