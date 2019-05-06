# SlicerHCCCaseIterator

SlicerHCCCaseIterator is a scripted module extension for 3D slicer. It is a customized version of the 
SlicerCaseIterator built specifically for annotation of MRI abdomen studies before and after a treatment.
It's purpose is to streamline the segmentation of image datasets by handling
loading and saving. This customized version for HCC labeling pre- and post-treatment requires a specific
naming convention and is used in conjunction with custom DICOM to nifti conversion/deidentification script
that can be found at 

## Usage

### Input Data
The input for SlicerHCCCaseIterator is a csv-file containing the folder path for each subject which contains
images and/or labelmaps that have to be segmented. The first row should be a header row, with
each subsequent row representing one subject.

In this version of the CaseIterator the first subject in the csv-file can be automatically loaded upon
start-up of Slicer by including the following script in the .slicerrc.py file (typically found in user home folder):

# Python commands in this file are executed on Slicer startup
  
  ## Go to SlicerCaseIterator on StartUp

  slicer.util.selectModule("SlicerCaseIterator")

  ## Autoload given .csv file

  logic = slicer.modules.tables.logic()
  newTable = logic.AddTable("/Users/brettmarinelli/Dropbox/IR_Work/Y90_Seg_segmentations/Review_DC.csv") ##Location of csv-file
  sciw = slicer.modules.slicercaseiterator.widgetRepresentation().self()
  sciw.batchTableSelector.setCurrentNode(newTable)
  sciw.batchTableView.setMRMLTableNode(newTable)
  sciw.txtReaderName.text = 'DC' ##Set the annotator initials for new segments that are created 
                                 ##and automatic loading of exiting annotations by this reader in subject folder
  sciw.onReset()  ##Automatically starts case iterator

If automatic launching is not desired in the home screen of the SlicerHCCCaseITerator and if you already 
processed some part of the batch or need to start at a specific case, you can do so by specifying the 
number at the `Start postion` parameter (with 1 representing the first case).

When input data is valid, press `Start Batch` and start segmenting!

### Case Navigation

When a batch is loaded, the users can navigate between cases using the `Previous Case` and `Next Case`
buttons that are then visible on the module interface.

In addition to the buttons, navigation also be controlled using 2 keyboard shortcuts:
- `Ctrl + N`: Go to next case
- `Ctrl + P`: Go to previous case (in case the first case is active, nothing happens)

When the last case is selected and the user moves to the next case, the current case is closed
and a message indicating the batch is done is shown (navigation is then disabled).

Exiting the navigation prior to reaching is possible using the `Reset` button,
which exits the navigation (the case is not saved and not closed).

New segmentations will automatically be saved using a hard-coded naming convention and the
designated reader initials when advancing to the next case so manually saving is not required.

### Console Output

On the python console SlicerCaseIterator prints information about the current case.
Output can contain the following:
- The case number that is loaded. If the table contains a column `patient` or `ID`, the value
  of this cell for the current row is added to this message, e.g. `Loading next patient (3/5): breast1...` 
- An info messages when the case is closed.
- For each new file that is saved, the full path location of the new file is printed.
- Errors and warnings about invalid or missing input.

- Additional information is loaded in this customized version which notes which files were
loaded successfully

### Invalid input

When the input is invalid (e.g. unknown column, incorrect path), error messages
detailing the error are shown.

### Output Customization

The following customization is available when processing a batch of cases:
- `Reader name`: Any string specified here gets appended to filenames used to save labelmaps
  (both new labelmaps and labelmaps that were specified in the input file). This can help to
  prevent inadvertently overwriting files and to keep track of who made the labelmaps.
- `Go to Editor`: Check this to automatically switch to the editor module whenever a new case is loaded.
  
When both `Save loaded masks` and `Save new masks` are unchecked, nothing is saved, and SlicerCaseIterator will
only show you the cases. **N.B. any newly added labelmaps and changes are discarded when the user switches
to a different case!**
