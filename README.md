
# cmd-national-population-projections

Transforms an input file (consisting of a xip file of xml) into 7 datasets.

example source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/z1zippedpopulationprojectionsdatafilesuk


# Usage

`python natPP.py <name of <zipfile>`

Creates a master file called `Npp_Extracted_<name of zipfile>.csv` which is a V4 shaped extraction of all the xml data.

Use the jupyter notebook `Pop Projections Transform.ipynb` to splt this into the required datasets.

