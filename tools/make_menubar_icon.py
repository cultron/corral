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

    import math

    def arc(cx, cy, rx, ry, t0, t1, width, steps=48):
        """Elliptical arc; angles in degrees, y-down design coords (90 = bottom)."""
        p = AppKit.NSBezierPath.bezierPath()
        for i in range(steps + 1):
            t = math.radians(t0 + (t1 - t0) * i / steps)
            pt = (cx + rx * math.cos(t), Y(cy + ry * math.sin(t)))
            p.moveToPoint_(pt) if i == 0 else p.lineToPoint_(pt)
        stroke(p, width)

    # An oval corral seen from slightly above: a thin far rail, two
    # heavier near rails, and posts along the near side.
    cx, rx, ry = 9.0, 7.4, 3.4
    top_rail, bot_rail = 7.4, 10.6      # ellipse centers (y) of the two rails
    arc(cx, top_rail, rx, ry, 180, 360, 1.2)             # far side of the upper rail
    arc(cx, top_rail, rx, ry, 0, 180, 1.7)               # near side, upper rail
    arc(cx, bot_rail, rx, ry, 0, 180, 1.7)               # near side, lower rail
    for deg in (150, 90, 30):                            # posts on the near side
        x = cx + rx * math.cos(math.radians(deg))
        dy = ry * math.sin(math.radians(deg))
        line(x, top_rail + dy - 1.9, x, bot_rail + dy + 1.9, 2.0)

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
