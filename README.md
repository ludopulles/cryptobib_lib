# CryptoBib Libraries

**WARNING**: This is probably not the repository your are interested in. This repository is only for *cryptobib* developers. The repositories containing the public *bib* files are [cryptobib/export](https://github.com/cryptobib/export) and  [cryptobib/export_crossref](https://github.com/cryptobib/export_crossref).

**WARNING**: This project shall only be used as a subfolder of the main project [cryptobib/cryptobib](https://github.com/cryptobib/cryptobib). Please read the documentation of the main project.


## Mybibtex

Mybibtex contains customized versions of some `pybtex` files (https://pybtex.org/) to prevent field values to be flattened to a string (and instead be stored as `Value`, see `mybibtex/database.py`. This is necessary to be able to generate files actually using macros.
It also contains a custom way of printing bibtex entries (`generator.py`).