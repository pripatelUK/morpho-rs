"""Render the vault history page by embedding a dataset into the HTML template.

Usage: python3 -I render_page.py <dataset.json> <out.html> [template.html]
"""
import os
import sys

DATASET, OUT = sys.argv[1], sys.argv[2]
TEMPLATE = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), "page", "template.html")

data = open(DATASET).read()
# The dataset is inlined in a <script> tag, so it must not be able to close it.
if "</" in data:
    sys.exit("dataset contains '</', which would break out of the <script> tag")

template = open(TEMPLATE).read()
if template.count("__DATA__") != 1:
    sys.exit("template must contain exactly one __DATA__ placeholder")

open(OUT, "w").write(template.replace("__DATA__", data))
print("wrote", OUT)
