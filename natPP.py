# -*- coding: utf-8  -*-
from bs4 import BeautifulSoup
import pandas as pd
import zipfile, sys

# ##############################
# Constants Used for validation

EXPECTED_NAMED_RANGES = ('Births', 'Cross_border_migration', 'Cross_border_rates', 'Deaths', 'Fertility_assumptions', 'International_migration', 'Mortality_assumptions', 'Population', 'Total_migration')
EXPECTED_PROJECTION_TYPE_IDENTIFIERS = ["hhh","hpp","lll","lpp","php","plp","pph","ppl","ppp","ppz"]


# get the projection type for a given xml
def getProjectionOrGeography(XMLsoup, wanted):
    
    allTabs = XMLsoup.find_all("worksheet")
    for at in allTabs:
        if at.attrs['ss:name'] == 'Contents':
            contents = at
            
    rows = contents.find_all('row')
    
    for r in rows:
        if wanted in r.text:

            found = r.find_all('data')[1].text

            print ("Setting '{w}' as: '{f}'".format(w=wanted,f=found))
            return found
    

# Returns a list of dictionaries, one for each tab. 
# Each dict has the projection type and a dataframe equating to one "tab" worth of data
def dataFramesFromXML(XMLsoup, tabDict):
    
    # get the projection type and geography for the XML file
    projectionType = getProjectionOrGeography(XMLsoup, 'Projection type:')

    
    geoCoverage = getProjectionOrGeography(XMLsoup, 'Coverage')
    
    if geoCoverage == "United Kingdom (uk)":
        geoCoverage = "K02000001"
    else:
        raise ValueError('Expecting geographic area of "United Kingdom (uk)" in the contents tab but its not there. Aborting.')
    
    
    allFrames = []
    processedTabs = []
    for tab in tabDict:

        currentSheet = XMLsoup.find("worksheet",{"ss:name":tab['name']})

        cells = currentSheet.find_all('cell')

        currentRow = 0
        dFrame = {}
        mapValues = {}

        for c in cells:

            # First run down the row is getting column headers mapped. Then we fill them.
            if currentRow < int(tab['rowCount']):
                mapValues.update({currentRow:c.text.strip()})
                dFrame.update({c.text.strip():[]})
            else:
                colName = mapValues[currentRow % int(tab['rowCount'])]
                dFrame[colName].append(c.text.strip())
            currentRow += 1

        allFrames.append({'df':pd.DataFrame.from_dict(dFrame), 'coverage':geoCoverage, 'projection':projectionType, 'tab':tab['name']})

        processedTabs.append(tab["name"])

    if set(processedTabs) == EXPECTED_NAMED_RANGES:
        raise ValueError("Aborting. Expecting to have processed `{exp}` instead processed {did}".format(exp=",".join(list(EXPECTED_NAMED_RANGES)),did=",".join(processedTabs)))
        
    return allFrames
    

"""
Extracts name and number of rows for each "tab" of data in the xml file

return [
        {'name':'Births', 'rowCount':27},
        etc..
        ]
"""
def tabDetailsFromXML(XMLsoup):
    
    sheets = XMLsoup.find_all('namedrange')
    
    tabs = []
    for sheet in sheets:

        namedRange = sheet.attrs['ss:name'].strip()
        if namedRange not in EXPECTED_NAMED_RANGES:
            print("Disregarding unwanted named range '" + namedRange + "'")
        else:

            print("Extracting: ", namedRange)
        
            ref = sheet.attrs['ss:refersto'].split(':')[-1]

            if 'C' not in ref:
                raise ValueError("Couldn't find `C` in: " + sheet.attrs['ss:refersto'])

            ref = ref.split('C')[1]

            details = {
                'name':sheet.attrs['ss:name'].strip(),
                'rowCount':ref
                      }
            tabs.append(details)
    
    return tabs
    

# Build a v4 file from our list of dataframes
def buildV4(dfList):
    
    v4ToJoin = []
    for dfItem in dfList:
        v4Pieces = []
        
        df = dfItem['df']
        tabName = dfItem['tab']
        projection = dfItem['projection']
        coverage = dfItem['coverage']
        
        for col in df.columns.values:
            if col.lower().strip() != 'sex' and col.lower().strip() != 'age' and  col.lower().strip() != 'flow':
                
                newDf = pd.DataFrame()
                newDf['V4_0'] = df[col]
                
                newDf['time'] = col
                newDf['time_codelist'] = 'Year'

                newDf['geography'] = ''
                newDf['geography_codelist'] = coverage
                
                newDf['sex_codelist'] = ''
                newDf['sex'] = df['Sex']
                newDf[newDf['sex'] == 1] = 'Male'
                newDf[newDf['sex'] == 2] = 'Female'
                
                newDf['age_codelist'] = ''
                newDf['age'] = df['Age']
                
                newDf['projectiontype_codelist'] = ''
                newDf['projectiontype'] = projection
                    
                newDf['populationmeasure_codelist'] = ''
                newDf['populationmeasure'] = tabName
                
                if 'migration' in tabName.lower() and len(newDf) > 1:
                    newDf['populationmeasure'] = newDf['populationmeasure']  + "(" + df['Flow'] + ")"

                v4Pieces.append(newDf)
        v4ToJoin.append(pd.concat(v4Pieces))

    allV4 = pd.concat(v4ToJoin)

    return postProcess(allV4)


# takes two columns, creates codelists in colA using the values in colB
def codeListify(df, colA, colB):

    # embedded function, changes individual cells
    def changeValueToCode(cell):

        cell = str(cell)
        cell = cell.lower().replace(" ","-")
        return cell

    df[colA] = df[colB].apply(changeValueToCode)

    return df


def postProcess(df):

    columnsToPostProcess = ["age_codelist", "sex_codelist", "projectiontype_codelist", "populationmeasure_codelist", "geography"]

    # Make sure we actually have the columns we're expecting
    for col in columnsToPostProcess:
        if col not in df.columns.values:
            raise ValueError("Aborting. Could not find mandatory column {c} during post processing.".format(c=col))

    df = codeListify(df, "sex_codelist", "sex")
    df = codeListify(df, "age_codelist", "age")
    df = codeListify(df, "projectiontype_codelist", "projectiontype")
    df = codeListify(df, "populationmeasure_codelist", "populationmeasure")

    # Geography
    df["geography"][df["geography_codelist"] == "K02000001"] = "United Kingdom"

    return df


def oneFileToV4(inFile): 

    with open(inFile, 'r') as f:

        # Parse with bs4
        soup = BeautifulSoup(f, 'lxml')
        
        # Get the tabs
        tabDict = tabDetailsFromXML(soup)
        
        # Get the data for each tab into a dataframe
        dfList = dataFramesFromXML(soup, tabDict)
        
        # Build V4
        v4 = buildV4(dfList)
    
    return v4


def extractFromZip(filename, oneCube=False):
    
    z = zipfile.ZipFile(filename)
    z.extractall()
    xmlFiles = [x for x in z.namelist() if '.xml' in x]
    
    allV4 = []
    for xml in xmlFiles:

        projectionTypeIDentifier = xml.split("_")[1]
        if projectionTypeIDentifier not in EXPECTED_PROJECTION_TYPE_IDENTIFIERS:
            print("\nNot Processing {f} as `{i}` is an unknown or experimental projection type.".format(f=xml,i=projectionTypeIDentifier))
        else:
            print("\nProcessing: " + xml)

            v4 = oneFileToV4(xml)
            allV4.append(v4)
        
    final = pd.concat(allV4)

    final.to_csv('Experimental-National Population Projections.csv', index=False)


if __name__ == "__main__":
    inFile = sys.argv[1]
    extractFromZip(inFile)
