# Agent instructions: Transparent PNG Lab

You are working in a local macOS/Linux project whose goal is to create **true transparent PNGs** with a real alpha channel and no baked checkerboard pixels.

## Core rule

Do not generate or request a checkerboard, transparency grid, fake transparent preview, or “PNG background.” Generate the subject on a flat removable background, then run the pipeline.

## Workflow

1. Create or obtain a source image.
2. The source should be isolated on a flat matte light-gray background, preferably around `#e6e6e6`.
3. Keep the full object visible. Avoid floor, shadow, reflection, border, scene, and textured background.
4. Save the source image into `inputs/`, usually:

   ```bash
   inputs/generated.png
   ```

5. Run:

   ```bash
   ./tpng process inputs/generated.png --open
   ```

6. In the preview, inspect variants over black, white, magenta, blue, mid-gray, and other swatches.
7. Choose only a variant whose PNG has real alpha and no checkerboard traces.

## Good prompt pattern

```text
[subject], centered, full object visible, clean silhouette, isolated on a flat matte light gray background, studio product cutout, no floor, no environment, no cast shadow, no reflection, no border
```

## Avoid in positive prompt

```text
transparent background, PNG, alpha channel, checkerboard, transparency grid, cutout on checkerboard
```

## Negative prompt, when supported

```text
checkerboard, transparency grid, tiled background, gray squares, textured background, drop shadow, reflection, floor, border, frame
```

## Commands

```bash
./tpng doctor
./tpng process inputs/generated.png --open
./tpng web
./tpng verify runs/<run>/variants/<variant>/final.png
```

If the user starts with an already-generated image, skip image generation and run the pipeline on that file.
