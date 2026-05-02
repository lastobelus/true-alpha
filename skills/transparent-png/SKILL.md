# Transparent PNG skill

## Goal

Produce a true RGBA transparent PNG with no baked checkerboard pixels.

## Steps

1. Generate or obtain a normal source image with the subject isolated on a flat matte light-gray background.
2. Save it to `inputs/generated.png` unless the user supplied another path.
3. Run:

   ```bash
   ./tpng process inputs/generated.png --open
   ```

4. Inspect variants in the HTML preview over multiple solid backgrounds.
5. Save the best variant through the preview UI.

## Never do this

Do not ask the image generator for checkerboards, transparency grids, or fake transparent previews.

## Prompt pattern

```text
[subject], centered, full object visible, clean silhouette, isolated on a flat matte light gray background, studio product cutout, no floor, no environment, no cast shadow, no reflection, no border
```
