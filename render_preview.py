"""Render preview images of the generated STLs (run dagger.py first)."""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIGHT_DIR = np.array([0.3, -0.5, 0.8]) / np.linalg.norm([0.3, -0.5, 0.8])


def drawMesh(ax, mesh, elev, azim, title):
    shade = np.clip(mesh.face_normals @ LIGHT_DIR, 0, 1) * 0.75 + 0.2
    colors = np.column_stack([shade * 0.55, shade * 0.58, shade * 0.62, np.ones_like(shade)])
    ax.add_collection3d(Poly3DCollection(mesh.triangles, facecolors=colors, linewidths=0))
    low, high = mesh.bounds
    ax.set_xlim(low[0], high[0])
    ax.set_ylim(low[1], high[1])
    ax.set_zlim(low[2], high[2])
    ax.set_box_aspect(tuple(high - low))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title)


def main():
    mesh = trimesh.load(os.path.join(BASE_DIR, "stl", "dagger_full.stl"))
    views = [(90, -90, "Top (blade flat)"), (30, -60, "Perspective"), (0, -90, "Side (edge-on)")]
    fig = plt.figure(figsize=(16, 12))
    for i, (elev, azim, title) in enumerate(views):
        drawMesh(fig.add_subplot(3, 1, i + 1, projection="3d"), mesh, elev, azim, title)
    plt.tight_layout()
    outPath = os.path.join(BASE_DIR, "images", "preview.png")
    fig.savefig(outPath, dpi=130)
    print("wrote", outPath)


if __name__ == "__main__":
    main()
