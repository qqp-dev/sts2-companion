"""Read-only, source-first extraction support for pinned StS2 inputs.

Modules parse PE/CLI metadata, CIL method bodies, and selected PCK entries as
bytes. They never load or execute the shipped assembly or initialize Godot.
"""

EXTRACTOR_VERSION = "14.0.0"
SCHEMA_VERSION = 14
