# MGTools - Metal Gear Tools

Collection of various tools for PC ports of Metal Gear / Metal Gear 2: Solid Snake!

Table of Contents
-----------------
- [Support](#support)
- [Features](#features)
- [Requirements](#build-requirements)
- [Installing](#installing)
- [Usage](#usage)
- [Credits](#credits)

Support
-------
The following games are supported by MGTools:

Game                                        | Supported
--------------------------------------------|----------
Metal Gear (GOG)                            | ✔️
Metal Gear Master Collection (Steam)        | ✔️
Metal Gear 2: Solid Snake Master Collection | 🚧


Features
--------

MGTools provides the following utilities:

- **Export and Import resource files from Metal Gear 1**:  
  Allows you to extract and rebuild MG1 resource files.
  - Export: Extract all files from a resource to a directory.
  - Import: Pack a directory of files into a new resource file.

Unsupported/Unknown files will be saved to `raw` subfolder during export.
And supported files will be converted to more user-friendly formats.

Table of Compatibility:

File Type      | Export | Import
---------------|--------|--------
Sprites        | ✔️     | ✔️ (to .png)
Palette        | ✔️     | ✔️ (to editable .xml)
Locale         | ✔️     | ✔️ (to .po files, and game scripts saved as-is in dedicated folder)
Fonts          | ✔️     | ✔️ (metadata will be saved as .xml, atlas bitmap can be saved as .png, or as bitmap-per-character)


Requirements
------------

- Python 3.11+

Installing
----------

Either use compiled portable build for Windows or Linux from [Releases](https://github.com/GrzybDev/MGTools/releases) page or use your python package management system (like `pipx` or `uv`)

Example:
`pipx install git+https://github.com/GrzybDev/MGTools.git`


Usage
-----

After installing the package, you can use the tools via the `mgtools` command (or `python -m mgtools` for local installs).

### General

```sh
mgtools --help
```

### Metal Gear 1

Export whole resource file to specified folder:
```sh
mgtools mg1 export path/to/resource.bin
mgtools mg1 export path/to/resource.bin path/to/output/dir
mgtools mg1 export path/to/resource.bin --separate-chars
mgtools mg1 export path/to/resource.bin path/to/output/dir --separate-chars
```

Generate new resource file from specified folder:
```sh
mgtools mg1 generate path/to/input/dir
mgtools mg1 generate path/to/input/dir path/to/output_file
```

---

Each command has its own help, e.g.:
```sh
mgtools mg1 --help
```

Credits
-------

- [GrzybDev](https://grzyb.dev)

Special thanks to:
- Konami (for publishing Metal Gear)
