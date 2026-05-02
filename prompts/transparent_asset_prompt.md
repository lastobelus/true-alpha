# Transparent asset source-image prompt

Use this when asking an image model or an agent to create the **source image** for the pipeline.

```text
[subject], centered, full object visible, clean silhouette, isolated on a flat matte light gray background, studio product cutout, no floor, no environment, no cast shadow, no reflection, no border
```

Avoid:

```text
transparent background, PNG, alpha channel, checkerboard, transparency grid, cutout on checkerboard
```

Negative prompt, if the tool supports one:

```text
checkerboard, transparency grid, tiled background, gray squares, textured background, drop shadow, reflection, floor, border, frame
```
