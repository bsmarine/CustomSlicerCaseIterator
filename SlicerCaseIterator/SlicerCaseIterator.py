# =========================================================================
#  Copyright Joost van Griethuysen
#
#  Licensed under the 3-Clause BSD-License (the "License");
#  you may not use this file except in compliance with the License.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ========================================================================

import csv
from collections import OrderedDict
import logging
import os
import datetime
import numpy as np

import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *


# ------------------------------------------------------------------------------
# SlicerCaseIterator
# ------------------------------------------------------------------------------
class SlicerCaseIterator(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = 'Case Iterator HCC'
    self.parent.categories = ['Utilities']
    self.parent.dependencies = []
    self.parent.contributors = ["Joost van Griethuysen (AVL-NKI)"]
    self.parent.helpText = """
    This is a scripted loadable module to iterate over a batch of images (with/without prior segmentations) for segmentation or review.
    """
    self.parent.acknowledgementText = "This work is covered by the 3-clause BSD License. No funding was received for this work."


# ------------------------------------------------------------------------------
# SlicerCaseIteratorWidget
# ------------------------------------------------------------------------------
class SlicerCaseIteratorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  # New feature: load the input as a table and show in in de module panel
  # tableNode = slicer.vtkMRMLTableNode()
  # slicer.mrmlScene.AddNode(tableNode)

  # tableView=slicer.qMRMLTableView()
  # tableView.setMRMLTableNode(tableNode)
  # tableView.show()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    #Set Two Over Two View

    layoutManagerApp = slicer.app.layoutManager()
    layoutManagerApp.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutTwoOverTwoView)

    # Setup a logger for the extension log messages
    self.logger = logging.getLogger('SlicerCaseIterator')

    # Instantiate some variables used during iteration
    self.csv_dir = None  # Directory containing the file specifying the cases, needed when using relative paths
    self.tableNode = None
    self.caseColumns = None  # Dictionary holding the specified (and found) columns from the batchTable
    self.currentCase = None  # Represents the currently loaded case
    self.caseCount = 0  # Counter equalling the total number of cases
    self.currentIdx = -1  # Current case index (starts at 0 for fist case, -1 means nothing loaded)

    # These variables hold connections to other parts of Slicer, such as registered keyboard shortcuts and
    # Event observers
    self.shortcuts = []
    self.observers = []

    # Instantiate and connect widgets ...

    #
    # Select and Load input data section
    #

    self.inputDataCollapsibleButton = ctk.ctkCollapsibleButton()
    self.inputDataCollapsibleButton.text = 'Select and Load case data'
    self.layout.addWidget(self.inputDataCollapsibleButton)

    inputDataFormLayout = qt.QFormLayout(self.inputDataCollapsibleButton)

    #
    # Input CSV Path
    #
    self.inputPathSelector = ctk.ctkPathLineEdit()
    self.inputPathSelector.toolTip = 'Location of the CSV file containing the cases to process'
    inputDataFormLayout.addRow('Input CSV path', self.inputPathSelector)

    self.loadBatchButton = qt.QPushButton('Load Input Data')
    self.loadBatchButton.enabled = False
    self.loadBatchButton.toolTip = 'Load the select file into the input Table'
    inputDataFormLayout.addRow(self.loadBatchButton)

    self.batchTableSelector = slicer.qMRMLNodeComboBox()
    self.batchTableSelector.nodeTypes = ['vtkMRMLTableNode']
    self.batchTableSelector.addEnabled = True
    self.batchTableSelector.selectNodeUponCreation = True
    self.batchTableSelector.renameEnabled = True
    self.batchTableSelector.removeEnabled = True
    self.batchTableSelector.noneEnabled = False
    self.batchTableSelector.setMRMLScene(slicer.mrmlScene)
    self.batchTableSelector.toolTip = 'Select the table representing the cases to process.'
    inputDataFormLayout.addRow(self.batchTableSelector)

    self.batchTableView = slicer.qMRMLTableView()
    inputDataFormLayout.addRow(self.batchTableView)
    self.batchTableView.show()

    #
    # Parameters Area
    #
    self.parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    self.parametersCollapsibleButton.text = 'Parameters'
    self.layout.addWidget(self.parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(self.parametersCollapsibleButton)

    #
    # Input parameters GroupBox
    #

    self.inputParametersGroupBox = qt.QGroupBox('Input parameters')
    parametersFormLayout.addRow(self.inputParametersGroupBox)

    inputParametersFormLayout = qt.QFormLayout(self.inputParametersGroupBox)

    #
    # Start position
    #
    self.npStart = qt.QSpinBox()
    self.npStart.minimum = 1
    self.npStart.maximum = 999999
    self.npStart.value = 1
    self.npStart.toolTip = 'Start position in the CSV file (1 = first patient)'
    inputParametersFormLayout.addRow('Start position', self.npStart)

    #
    # Root Path
    #
    self.rootSelector = qt.QLineEdit()
    self.rootSelector.text = 'path'
    self.rootSelector.toolTip = 'Location of the root directory to load from, or the column name specifying said ' \
                                'directory in the input CSV'
    inputParametersFormLayout.addRow('Root Column', self.rootSelector)

    #
    # Image Path
    #
    self.imageSelector = qt.QLineEdit()
    self.imageSelector.text = 'image'
    self.imageSelector.toolTip = 'Name of the column specifying main image files in input CSV'
    inputParametersFormLayout.addRow('Image Column', self.imageSelector)

    #
    # Mask Path
    #
    self.maskSelector = qt.QLineEdit()
    self.maskSelector.text = 'mask'
    self.maskSelector.toolTip = 'Name of the column specifying main mask files in input CSV'
    inputParametersFormLayout.addRow('Mask Column', self.maskSelector)

    #
    # Additional images
    #
    self.addImsSelector = qt.QLineEdit()
    self.addImsSelector.text = ''
    self.addImsSelector.toolTip = 'Comma separated names of the columns specifying additional image files in input CSV'
    inputParametersFormLayout.addRow('Additional images Column', self.addImsSelector)

    #
    # Additional masks
    #
    self.addMasksSelector = qt.QLineEdit()
    self.addMasksSelector.text = ''
    self.addMasksSelector.toolTip = 'Comma separated names of the columns specifying additional mask files in input CSV'
    inputParametersFormLayout.addRow('Additional masks Column', self.addMasksSelector)

    #
    # Output parameters GroupBox
    #

    self.outputParametersGroupBox = qt.QGroupBox('Output parameters')
    parametersFormLayout.addRow(self.outputParametersGroupBox)

    outputParametersFormLayout = qt.QFormLayout(self.outputParametersGroupBox)

    #
    # Reader Name
    #
    self.txtReaderName = qt.QLineEdit()
    self.txtReaderName.text = ''
    self.txtReaderName.toolTip = 'Name of the current reader; if not empty, this name will be added to the filename ' \
                                 'of saved masks'
    outputParametersFormLayout.addRow('Reader name', self.txtReaderName)

    #
    # Auto-redirect to SegmentEditor
    #

    self.chkAutoRedirect = qt.QCheckBox()
    self.chkAutoRedirect.checked = 1
    self.chkAutoRedirect.toolTip = 'Automatically switch module to "SegmentEditor" when each case is loaded'
    outputParametersFormLayout.addRow('Go to Segment Editor', self.chkAutoRedirect)

    #
    # Save masks
    #
    self.chkSaveMasks = qt.QCheckBox()
    self.chkSaveMasks.checked = 1
    self.chkSaveMasks.toolTip = 'save all initially loaded masks when proceeding to next case'
    outputParametersFormLayout.addRow('Save loaded masks', self.chkSaveMasks)

    #
    # Save masks
    #
    self.chkSaveNewMasks = qt.QCheckBox()
    self.chkSaveNewMasks.checked = 1
    self.chkSaveNewMasks.toolTip = 'save all newly generated masks when proceeding to next case'
    outputParametersFormLayout.addRow('Save new masks', self.chkSaveNewMasks)

    #
    # Previous Case
    #

    self.previousButton = qt.QPushButton('Previous Case')
    self.previousButton.enabled = False
    self.previousButton.toolTip = '(Ctrl+P) Press this button to go to the previous case, previous new masks are not reloaded'
    self.layout.addWidget(self.previousButton)

    #
    # Load CSV / Next Case
    #
    self.nextButton = qt.QPushButton('Next Case')
    self.nextButton.enabled = False
    self.nextButton.toolTip = '(Ctrl+N) Press this button to go to the next case'
    self.layout.addWidget(self.nextButton)

    #
    # Reset
    #
    self.resetButton = qt.QPushButton('Start Batch')
    self.resetButton.enabled = False
    self.layout.addWidget(self.resetButton)

    self.layout.addStretch(1)

    #
    # Connect buttons to functions
    #

    self.batchTableSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onChangeTable)

    self.loadBatchButton.connect('clicked(bool)', self.onLoadBatch)
    self.previousButton.connect('clicked(bool)', self.onPrevious)
    self.nextButton.connect('clicked(bool)', self.onNext)
    self.resetButton.connect('clicked(bool)', self.onReset)

    self._setGUIstate(csv_loaded=False)

  #------------------------------------------------------------------------------
  def cleanup(self):
    if self.currentIdx >= 0:
      self._setGUIstate(csv_loaded=False)  # Reset the GUI to ensure observers and shortcuts are removed
      self.currentCase = None
      self.caseColumns = None
      self.currentIdx = -1

  #------------------------------------------------------------------------------
  def onLoadBatch(self):
    if os.path.isfile(self.inputPathSelector.currentPath):
      self.logger.info('Loading %s...' % self.inputPathSelector.currentPath)
      logic = slicer.modules.tables.logic()
      newTable = logic.AddTable(self.inputPathSelector.currentPath)  # 2nd argument (string) can set the table name
      self.batchTableSelector.setCurrentNode(newTable)
      self.batchTableView.setMRMLTableNode(newTable)

  #------------------------------------------------------------------------------
  def onReset(self):
    if self.currentIdx < 0:
      # Lock GUI during loading
      self.previousButton.enabled = False
      self.nextButton.enabled = False
      self.resetButton.enabled = False
      self.nextButton.text = 'Loading...'

      if self._startBatch(start=self.npStart.value):
        self.loadCase(0)  # Load the currently selected case
    else:
      self._setGUIstate(csv_loaded=False)
      self.currentCase = None
      self.caseColumns = None
      self.currentIdx = -1

  #------------------------------------------------------------------------------
  def onChangeTable(self):
    self.resetButton.enabled = (self.batchTableSelector.currentNodeID != '')
    self.batchTableView.setMRMLTableNode(self.batchTableSelector.currentNode())

  #------------------------------------------------------------------------------
  def onPrevious(self):
    if self.currentIdx < 0:
      return

    self.loadCase(-1)

  #------------------------------------------------------------------------------
  def onNext(self):
    if self.currentIdx < 0:
      return

    self.loadCase(1)

  #------------------------------------------------------------------------------
  def onEndClose(self, caller, event):
    if self.currentCase is not None:
      self.currentCase = None
      self.logger.info('case closed')
    if self.tableNode is not None:
      slicer.mrmlScene.AddNode(self.tableNode)
      self.batchTableSelector.setCurrentNode(self.tableNode)
      self.batchTableView.setMRMLTableNode(self.tableNode)

  #------------------------------------------------------------------------------
  def loadCase(self, idx_change):
    """
    If a batch of cases is loaded, this function proceeds to the next case. If a current case is open, it is saved
    and closed. Next, a new case is obtained from the generator, which is then loaded as the new ``currentCase``.
    If the last case was loaded, the iterator exits and resets the GUI to allow for loading a new batch of cases.
    """
    if self.currentIdx < 0:
      return

    if self.currentIdx + idx_change < 0:
      # Cannot select a negative index, so give a warning and exit the function
      self.logger.warning('First case selected, cannot select previous case!')
      return

    # If a case is open, save it and close it before attempting to load a new case
    if self.currentCase is not None:
      self.currentCase.closeCase(save_loaded_masks=(self.chkSaveMasks.checked == 1),
                                 save_new_masks=(self.chkSaveNewMasks.checked == 1),
                                 reader_name=self.txtReaderName.text)

    # Attempt to load a new case. If the current case was the last one, a
    # StopIteration exception will be raised and handled, which resets the
    # GUI to allow loading another batch of cases

    self.currentIdx += idx_change
    if self.currentIdx >= self.caseCount:
      self._setGUIstate(csv_loaded=False)
      self.currentIdx = -1
      self.tableNode = None
      self.logger.info('########## All Done! ##########')
      return

    # Lock GUI during loading
    self.previousButton.enabled = False
    self.nextButton.enabled = False
    self.resetButton.enabled = False
    self.nextButton.text = 'Loading...'

    if 'patient' in self.caseColumns:
      patient = self.caseColumns['patient'].GetValue(self.currentIdx)
      self.logger.info('Loading next patient (%d/%d): %s...', self.currentIdx + 1, self.caseCount, os.path.basename(patient))
    else:
      self.logger.info('Loading next patient (%d/%d)...', self.currentIdx + 1, self.caseCount)

    settings = {}

    root = self._getColumnValue('root')  # Root specified in the batch table? If not, None is returned
    if root is None and self.rootSelector.text != '':
      root = self.rootSelector.text  # Root specified as a path
    if root is not None:
      settings['root'] = root

    # image = self._getColumnValue('image')
    # mask = self._getColumnValue('mask')

    addIms = self._getColumnValue('addIms', True)
    
    if addIms is not None:
      settings['addIms'] = addIms
    addMas = self._getColumnValue('addMas', True)
    if addMas is not None:
      settings['addMas'] = addMas

    settings['csv_dir'] = self.csv_dir
    settings['redirect'] = (self.chkAutoRedirect.checked == 1)

#    self.currentCase = SlicerCaseIteratorLogic(image, mask, **settings)

    self.currentCase = SlicerCaseHCCIteratorLogic(patient,self.txtReaderName.text, **settings)

    # Unlock GUI
    self.previousButton.enabled = True
    self.nextButton.enabled = True
    self.resetButton.enabled = True
    self.nextButton.text = 'Next Case'

    print ("Patient: "+os.path.basename(patient))

  #------------------------------------------------------------------------------
  def _getColumnValue(self, colName, is_list=False):
    if colName not in self.caseColumns:
      return None

    if is_list:
      return [col.GetValue(self.currentIdx) for col in self.caseColumns[colName]]
    else:
      return self.caseColumns[colName].GetValue(self.currentIdx)

  #------------------------------------------------------------------------------
  def _startBatch(self, start=1):

    self.caseColumns = {}
    self.tableNode = self.batchTableSelector.currentNode()

    # If the table was loaded from a file, get the directory containing the file as reference for relative paths
    if self.tableNode.GetStorageNode() is not None and self.tableNode.GetStorageNode().GetFileName() is not None:
      self.csv_dir = os.path.dirname(self.tableNode.GetStorageNode().GetFileName())
    else:  # Table did not originate from a file
      self.csv_dir = None

    batchTable = self.batchTableSelector.currentNode().GetTable()

    self.caseCount = batchTable.GetNumberOfRows()

    # Return generator to iterate over all cases
    if self.caseCount < start:
      self.logger.warning('No cases to process (%d cases, start %d)', self.caseCount, start)
      return False

    patientColumn = batchTable.GetColumnByName('patient')
    if patientColumn is None:
      patientColumn = batchTable.GetColumnByName('ID')
    if patientColumn is not None:
      self.caseColumns['patient'] = patientColumn

    if self.rootSelector.text != '':
      rootColumn = batchTable.GetColumnByName(self.rootSelector.text)
      if rootColumn is not None:
        self.caseColumns['root'] = rootColumn
      else:
        self.logger.warning('Unable to find column %s', self.rootSelector.text)

    if self.imageSelector.text != '':
      imageColumn = batchTable.GetColumnByName(self.imageSelector.text)
      if imageColumn is not None:
        self.caseColumns['image'] = imageColumn
      else:
        self.logger.warning('Unable to find column %s', self.imageSelector.text)
    if self.maskSelector.text != '':
      maskColumn = batchTable.GetColumnByName(self.maskSelector.text)
      if maskColumn is not None:
        self.caseColumns['mask'] = maskColumn
      else:
        self.logger.warning('Unable to find column %s', self.maskSelector.text)

    if self.addImsSelector.text != '':
      addIms = []
      for addIm in str(self.addImsSelector.text).split(','):
        addImColumn = batchTable.GetColumnByName(addIm.strip())
        if addImColumn is not None:
          addIms.append(addImColumn)
        else:
          self.logger.warning('Unable to find column %s', addIm)
      if len(addIms) > 0:
        self.caseColumns['addIms'] = addIms

    if self.addMasksSelector.text != '':
      addMas = []
      for addMa in str(self.addMasksSelector.text).split(','):
        addMaColumn = batchTable.GetColumnByName(addMa.strip())
        if addMaColumn is not None:
          addMas.append(addMaColumn)
        else:
          self.logger.warning('Unable to find column %s', addMa)
      if len(addMas) > 0:
        self.caseColumns['addMas'] = addMas

    self._setGUIstate()
    self.currentIdx = start - 1

    return True

  #------------------------------------------------------------------------------
  def _setGUIstate(self, csv_loaded=True):
    if csv_loaded:
      self.resetButton.text = 'Reset'

      # Collapse input parameter sections
      self.inputDataCollapsibleButton.collapsed = True
      self.parametersCollapsibleButton.collapsed = True

      # Connect the CTRL + N Shortcut
      if len(self.shortcuts) == 0:
        shortcutNext = qt.QShortcut(slicer.util.mainWindow())
        shortcutNext.setKey(qt.QKeySequence('Ctrl+N'))

        shortcutNext.connect('activated()', self.onNext)
        self.shortcuts.append(shortcutNext)

        shortcutPrevious = qt.QShortcut(slicer.util.mainWindow())
        shortcutPrevious.setKey(qt.QKeySequence('Ctrl+P'))

        shortcutPrevious.connect('activated()', self.onPrevious)
        self.shortcuts.append(shortcutPrevious)
      else:
        self.logger.warning('Shortcuts already initialized!')

      # Add an observer for the "MRML Scene End Close Event"
      if len(self.observers) == 0:
        self.observers.append(slicer.mrmlScene.AddObserver(slicer.mrmlScene.EndCloseEvent, self.onEndClose))
      else:
        self.logger.warning('Event observer already initialized!')
    else:
      # reset Button is locked when loading cases, ensure it is unlocked to load new batch
      self.resetButton.enabled = (self.batchTableSelector.currentNodeID != '')
      self.resetButton.text = 'Start Batch'

      # Remove the keyboard shortcut
      for sc in self.shortcuts:
        sc.disconnect('activated()')
        sc.setParent(None)
      self.shortcuts = []

      # Remove the event observer
      for obs in self.observers:
        slicer.mrmlScene.RemoveObserver(obs)
      self.observers = []

    self.previousButton.enabled = csv_loaded
    self.nextButton.enabled = csv_loaded

    self.inputPathSelector.enabled = not csv_loaded
    self.loadBatchButton.enabled = not csv_loaded
    self.batchTableSelector.enabled = not csv_loaded
    self.batchTableView.enabled = not csv_loaded
    self.inputParametersGroupBox.enabled = not csv_loaded


# ------------------------------------------------------------------------------
# SlicerCaseIteratorLogic
# ------------------------------------------------------------------------------
class SlicerCaseHCCIteratorLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self,subject,reader_name, **kwargs):
      self.logger = logging.getLogger('SlicerCaseIteratorHCC')

      self.volumesLoad = list()
      self.labelVolumesLoad = list()
      self.sub_dir = subject
      
      self.pre_T1_pre = None
      self.pre_T1_EA = None
      self.pre_T1_EA_sub = None
      self.pre_T1_LA = None
      self.pre_T1_LA_sub = None
      self.pre_T1_PV = None
      self.pre_T1_PV_sub = None
      self.pre_ADC = None
      self.post_T1_pre = None
      self.post_T1_EA = None
      self.post_T1_EA_sub = None
      self.post_T1_LA = None
      self.post_T1_LA_sub = None
      self.post_T1_PV = None
      self.post_T1_PV_sub = None
      self.post_ADC = None
      self.post_ADC_Eq_1 = None
      self.pre_ADC_Eq_1 = None
      self.pre_T1_label = None
      self.post_T1_label = None
      self.pre_ADC_label = None
      self.post_ADC_label = None

      root = kwargs.get('root', None)
      csv_dir = kwargs.get('csv_dir', None)



      self.root = None
      if root is not None:  # Root is specified as a directory
        if os.path.isabs(root) and os.path.isdir(root):  # Absolute path, use as it is
          self.root = root
        elif csv_dir is not None and os.path.isdir(os.path.join(csv_dir, root)):  # If it is a relative path, assume it is relative to the csv file location
          self.root = os.path.join(csv_dir, root)

      if self.root is None and csv_dir is not None and os.path.isdir(csv_dir):
        self.root = csv_dir

      self.addIms = kwargs.get('addIms', [])
      self.addMas = kwargs.get('addMas', [])
#    self.image = image
#    self.mask = mask
#
      self.GenerateMasks = kwargs.get('GenerateMasks', True)
      self.GenerateAddMasks = kwargs.get('GenerateAddMasks', True)
#
      self.redirect = kwargs.get('redirect', True)

      self.image_nodes = OrderedDict()
      self.mask_nodes = OrderedDict()
      self.reader_name = reader_name

    # Load images (returns True if loaded correctly) and check redirect:
    # if redirect = True, switch to SegmentEditor module or refresh to ensure user is prompted to add new segementation
      if self._loadImages(subject) and self.redirect:
        if slicer.util.selectedModule() == 'SegmentEditor':
          slicer.modules.SegmentEditorWidget.enter()
        else:
          slicer.util.selectModule('SegmentEditor')
          
      self.logger.debug('Case initialized (settings: %s)' % subject)

  #------------------------------------------------------------------------------
  def select_placeholder_for_view(self,subject_dir):

        raws,labels = self.load_data_to_placeholders(subject_dir)

        for i in raws:

            if i[1] == 0:
                self.pre_T1_pre = i[0]
            if i[1] == 1:
                self.pre_T1_EA = i[0]
            if i[1] == 2:
                self.pre_T1_EA_sub = i[0]
            if i[1] == 3:
                self.pre_T1_LA = i[0]
            if i[1] == 4:
                self.pre_T1_LA_sub = i[0]
            if i[1] == 5:
                self.pre_T1_PV = i[0]
            if i[1] == 6:
                self.pre_T1_PV_sub = i[0]
            if i[1] == 7:
                self.pre_ADC = i[0]
            if i[1] == 8:
                self.post_T1_pre = i[0]
            if i[1] == 9:
                self.post_T1_EA = i[0]
            if i[1] == 10:
                self.post_T1_EA_sub = i[0]
            if i[1] == 11:
                self.post_T1_LA = i[0]
            if i[1] == 12:
                self.post_T1_LA_sub = i[0]
            if i[1] == 13:
                self.post_T1_PV = i[0]
            if i[1] == 14:
                self.post_T1_PV_sub = i[0]
            if i[1] == 15:
                self.post_ADC = i[0]
            if i[1] == 16:
                self.post_ADC_Eq_1 = i[0]
            if i[1] == 17:
                self.pre_ADC_Eq_1 = i[0]

        for i in labels:
            if i[1] in [1,3]:
                print ("Found pre t1 label")
                self.pre_T1_label = i[0]
            if i[1] in [9,11]:
                print ("Found post t1 label")
                self.post_T1_label = i[0]
            if i[1] in [15,16]:
                print ("Found post ADC label")
                self.post_ADC_label = i[0]
            if i[1] in [7,17]:
                print ("Found pre ADC label")
                self.pre_ADC_label = i[0]

  def load_data_to_placeholders(self,subject_dir):
          self.image_root = subject_dir
          images = {'pre_T1_pre':0,'pre_T1_EA':1,'pre_T1_EA_sub':2,'pre_T1_LA':3,
                              'pre_T1_LA_sub':4,'pre_T1_PV':5,'pre_T1_PV_sub':6, 'pre_ADC':7,
                              'post_T1_pre':8,'post_T1_EA':9,'post_T1_EA_sub':10,'post_T1_LA':11,
                          'post_T1_LA_sub':12,'post_T1_PV':13,'post_T1_PV_sub':14,'post_ADC':15,
                              'post_ADC_Eq_1':16,'pre_ADC_Eq_1':17}
          
          raws = list()
          labels = list()
          for i in os.listdir(subject_dir):
                  file_name = i.lower()
                  for j,count in images.items():
                          if j.lower()+".nii.gz" in file_name:
                                  #print (j+" is found! Corresponding to filepath:"+str(i)+"And is given a count of "+str(count))
                                  img = slicer.util.loadVolume(os.path.join(subject_dir,i),returnNode=True)[1]
                                  raws.append([img,count])
                          if j.lower()+"_tumor_"+self.reader_name.lower()+".nii.gz" in file_name:
                                  #print (j+" is found! Corresponding to filepath:"+str(i)+"And is given a count of "+str(count))
                                  print ("Reader Name: "+self.reader_name)
                                  load_success, ma_node = slicer.util.loadLabelVolume(os.path.join(subject_dir,i), returnNode=True)
                                  seg_node = slicer.vtkMRMLSegmentationNode()
                                  slicer.mrmlScene.AddNode(seg_node)
                                  load_success = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(ma_node, seg_node) & load_success
                                  slicer.mrmlScene.RemoveNode(ma_node)
                                  seg_node.SetName(j+"_segment")
                                  segmentationDisplayNode = seg_node.GetDisplayNode()
                                  segmentationDisplayNode.VisibilityOff()
                                  labels.append([seg_node,count])
                                  #print (seg_node,count)

          return raws, labels

  def get_composite_node(self,sliceViewName):
            layoutManager = slicer.app.layoutManager()
            view = layoutManager.sliceWidget(sliceViewName).sliceView()
            sliceNode = view.mrmlSliceNode()
            sliceLogic = slicer.app.applicationLogic().GetSliceLogic(sliceNode)
            compositeNode = sliceLogic.GetSliceCompositeNode()
            return compositeNode
  def SliceGetID(self,sliceNode):
    return sliceNode.GetID()

  def GetName(self,node):
    return node.GetName()

  def correct_volumesLoad(self,volumesNode_list,labelmapNode_list):

  ## This module swaps late arterial for early arterial, or the ADC eq1 for the ADC
  ## in instances where the latter was used to make a segmentation and loads the appropriate
  ## background volume
    
    if labelmapNode_list[0] is not None:
      seg_name = labelmapNode_list[0].GetName()
      if self.post_T1_LA is not None:
        if seg_name[:seg_name.find("_segment")] in self.post_T1_LA.GetName():
          volumesNode_list[0] = self.post_T1_LA
    
    if labelmapNode_list[1] is not None:
      seg_name = labelmapNode_list[1].GetName()  
      if self.pre_T1_LA is not None:
        if seg_name[:seg_name.find("_segment")] in self.pre_T1_LA.GetName():
          volumesNode_list[1] = self.pre_T1_LA

    if labelmapNode_list[2] is not None:
      seg_name = labelmapNode_list[2].GetName()
      if self.post_ADC_Eq_1 is not None: 
        if seg_name[:seg_name.find("_segment")] in self.post_ADC_Eq_1.GetName():
          volumesNode_list[2] = self.post_ADC_Eq_1

    # if labelmapNode_list[3] is not None:
    #   seg_name = labelmapNode_list[3].GetName()
    #   if self.pre_ADC_Eq_1 is not None:
    #     if seg_name[:seg_name.find("_segment")] in self.pre_ADC_Eq_1.GetName():
    #       volumesNode_list[3] = self.pre_ADC_Eq_1

    return volumesNode_list

  def _loadImages(self,subject):

            start_load = datetime.datetime.now()

            self.select_placeholder_for_view(subject)

            self.volumesLoad = [self.post_T1_EA,self.pre_T1_EA,self.post_ADC, 
                                  self.pre_ADC]
            
            self.labelVolumesLoad = [self.post_T1_label,self.pre_T1_label,self.post_ADC_label,
                                                         self.pre_ADC_label]

            self.volumesLoad = self.correct_volumesLoad(self.volumesLoad,self.labelVolumesLoad)
            
            #Disable auto showing of master volume whenever segment editor loads or master volume is changed
            segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor

            segmentEditorWidget.setAutoShowMasterVolumeNode(False)
            
            #Load background volume to each view
            layoutManager = slicer.app.layoutManager()
            sliceViews = layoutManager.sliceViewNames()
            for i,sliceViewName in enumerate(sorted(sliceViews)):
              view = layoutManager.sliceWidget(sliceViewName).sliceView()
              sliceNode = view.mrmlSliceNode()
              sliceLogic = slicer.app.applicationLogic().GetSliceLogic(sliceNode)
              compositeNode = sliceLogic.GetSliceCompositeNode()

              
              try:
                print ("Loading Viewer "+str(compositeNode.GetSingletonTag())+" with Background Image "+str(self.volumesLoad[i].GetName()))
                compositeNode.SetBackgroundVolumeID(self.volumesLoad[i].GetID())

              except:
                print ("Failed Loading Viewer"+str(compositeNode.GetID()))
            
            #Load appropriate segmentation for to each view and set each view to 'axial'
            sliceNodes = slicer.util.getNodesByClass('vtkMRMLSliceNode')
            #print (sorted(sliceNodes,key=self.SliceGetID))
            for i,sliceNode in enumerate(sorted(sliceNodes, key=self.SliceGetID)):
              sliceNode.SetOrientation("Axial")
              #print ("Number: "+str(i)+" and View: "+str(sliceNode.GetName()))
              segNode = self.labelVolumesLoad[i]
              if self.volumesLoad[i] == None:
                pass
              elif self.labelVolumesLoad[i] == None:
                print ("No segmentation for view "+str(sliceNode.GetName()))
                print ("Making Empty "+str(self.volumesLoad[i].GetName())+" Segmentation for view "+str(sliceNode.GetName()))

                #Create New Segmentation Node
                segNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
                segNode.SetName(self.volumesLoad[i].GetName()+"_segment")
                segNode.SetReferenceImageGeometryParameterFromVolumeNode(self.volumesLoad[i])

                #Create New Segmentation Display Node for New Segmentation Node
                segmentationDisplayNode=slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationDisplayNode')
                segNode.AddAndObserveDisplayNodeID(segmentationDisplayNode.GetID())
                segmentationDisplayNode.SetDisplayableOnlyInView(sliceNode.GetID())

                #Add Empty Target and Background Segments to New Segmentation                
                segmentation = segNode.GetSegmentation()
                segmentation.AddEmptySegment("Target")
                segmentation.AddEmptySegment("Background")

                pass
              else:
                print ("For this view: "+str(sliceNode.GetName()))
                print ("Show Exisiting Segment Label: "+str(segNode.GetName()))
                segmentationDisplayNode = segNode.GetDisplayNode()
                segmentationDisplayNode.VisibilityOn()
                segmentationDisplayNode.SetDisplayableOnlyInView(sliceNode.GetID())
                segNode.SetReferenceImageGeometryParameterFromVolumeNode(self.volumesLoad[i])

            for sliceViewName in layoutManager.sliceViewNames():
              controller = layoutManager.sliceWidget(sliceViewName).sliceController()
              controller.fitSliceToBackground()

        
            # for i,viewNode in enumerate(viewNodes):
            #     try:
            #         viewNode.SetLabelVolumeID(self.labelVolumesLoad[i].GetID())
            #         viewNode.SetLabelOpacity(0.6)
            #     except:
            #         print ("Error Setting Foreground "+str(i))

            #self.center_images_in_all_views()
            #self.link_all_views()
            for sliceViewName in layoutManager.sliceViewNames():
              controller = layoutManager.sliceWidget(sliceViewName).sliceController()
              controller.fitSliceToBackground()
            end_load = datetime.datetime.now()
                        
            print (end_load - start_load)
            
            return True
    
  #  if self.root is None:
  #    self.logger.error('Missing root path, cannot load case!')
  #    return False

  #  if self.image is not None:
  #    self.addIms.append(self.image)
  #  if self.mask is not None:
  #    self.addMas.append(self.mask)
#
#    im_filepath = None
#    for im in self.addIms:
#      # Check if an image is specified
#      if im == '':
#        self.logger.warning('Empty path detected while loading volumes, skipping...')
#        continue
#      # Check if the path is absolute, else build a path relative from the root
#      if os.path.isabs(im):
#        im_filepath = im
#      else:
#        im_filepath = os.path.join(self.root, im)
#      # Check if the file actually exists
#      if not os.path.isfile(im_filepath):
#        self.logger.warning('Volume file %s does not exist, skipping...', im)
#
#      # Try to load the file
#      load_success, im_node = slicer.util.loadVolume(im_filepath, returnNode=True)
#      if not load_success:
#        self.logger.warning('Failed to load ' + im_filepath)
#        continue
#
#      # Use the file basename as the name for the loaded volume
#      im_node.SetName(os.path.splitext(os.path.basename(im_filepath))[0])
#      if im_node is not None:
#        self.image_nodes[im] = im_node
#
#    self.logger.debug('Loaded %d image(s)' % len(self.image_nodes))
#
#    for ma in self.addMas:
#      # Check if the mask is specified
#      if ma == '':
#        self.logger.warning('Empty path detected while loading segmentations, skipping...')
#        continue
#
#      # Check if the path is absolute, else build a path relative to the root
#      if os.path.isabs(ma):
#        ma_filepath = ma
#      else:
#        ma_filepath = os.path.join(self.root, ma)
#
#      # Check if the file actually exists
#      if not os.path.isfile(ma_filepath):
#        self.logger.warning('Segmentation file %s does not exist, skipping...', ma)
#      # Determine if file is segmentation based on extension
#      isSegmentation = (os.path.splitext(os.path.splitext(ma_filepath)[0]) == 'seg')
#      # Try to load the mask
#      if isSegmentation:
#        load_success, ma_node = slicer.util.loadSegmentation(ma_filepath, returnNode=True)
#      else:
#        # If not segmentation, then load as labelmap then import as segmentation
#        load_success, ma_node = slicer.util.loadLabelVolume(ma_filepath, returnNode=True)
#        seg_node = slicer.vtkMRMLSegmentationNode()
#        slicer.mrmlScene.AddNode(seg_node)
#        load_success = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(ma_node, seg_node) & load_success
#        slicer.mrmlScene.RemoveNode(ma_node)
#        ma_node = seg_node
#      if not load_success:
#        self.logger.warning('Failed to load ' + ma_filepath)
#        continue
#      # Use the file basename as the name for the newly loaded segmentation node
#      ma_node.SetName(os.path.splitext(os.path.basename(ma_filepath))[0])
#      if ma_node is not None:
#        self.mask_nodes[ma] = ma_node
#
#    self.logger.debug('Loaded %d mask(s)' % len(self.mask_nodes))
#
#    if len(self.image_nodes) > 0:
#      # Store the directory of the last loaded image (main image).
#      # This will be the directory where any output is saved
#      self.image_root = os.path.dirname(im_filepath)
#      self._rotateToVolumePlanes(self.image_nodes.values()[-1])
#
#    # If more than 1 image is loaded, set the next-to-last loaded image (i.e. the last 'additional image' as the
#    # ForegroundVolume in all three slice viewers.
#    if len(self.image_nodes) > 1:
#      slicer.app.layoutManager().sliceWidget('Red').sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(
#        self.image_nodes.values()[-2].GetID())
#      slicer.app.layoutManager().sliceWidget('Green').sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(
#        self.image_nodes.values()[-2].GetID())
#      slicer.app.layoutManager().sliceWidget('Yellow').sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(
#        self.image_nodes.values()[-2].GetID())
#

  #------------------------------------------------------------------------------
  def closeCase(self, save_loaded_masks=False, save_new_masks=False, reader_name=None):
    # Save the results (segmentations reviewed or created)
    
    if reader_name == '':
      reader_name = None

    print ("Saving Segmentations for "+reader_name)

    loaded_masks = {node.GetName(): node for node in self.mask_nodes.values()}
    new_masks = {node.GetName(): node for node in slicer.util.getNodesByClass('vtkMRMLSegmentationNode')
                 if node.GetName() not in loaded_masks.keys()}
    # If enabled, save segmentation
    if save_loaded_masks:
      if len(loaded_masks) == 0:
        self.logger.debug('No loaded masks to save...')
      else:
        self.logger.info('Saving %d loaded masks...', len(loaded_masks))
        self._saveMasks(loaded_masks, self.image_root, reader_name)
    if save_new_masks:
      if len(new_masks) == 0:
        self.logger.debug('No new masks to save...')
      else:
        self.logger.info('Saving %d new masks...', len(new_masks))
        self._saveMasks(new_masks, self.image_root, reader_name)

    # Close the scene and start a fresh one
    if slicer.util.selectedModule() == 'SegmentEditor':
      slicer.modules.SegmentEditorWidget.exit()

    slicer.mrmlScene.Clear(0)
    node = slicer.vtkMRMLViewNode()
    slicer.mrmlScene.AddNode(node)

  #------------------------------------------------------------------------------
  def _rotateToVolumePlanes(self, referenceVolume):
    sliceNodes = slicer.util.getNodes('vtkMRMLSliceNode*')
    for name, node in sliceNodes.items():
      node.RotateToVolumePlane(referenceVolume)
    # Snap to IJK to try and avoid rounding errors
    sliceLogics = slicer.app.layoutManager().mrmlSliceLogics()
    numLogics = sliceLogics.GetNumberOfItems()
    for n in range(numLogics):
      l = sliceLogics.GetItemAsObject(n)
      l.SnapSliceOffsetToIJK()
  #------------------------------------------------------------------------------
  def getMasterVolumeName(self):
    
    volNodeID = slicer.modules.SegmentEditorWidget.getDefaultMasterVolumeNodeID()
    volNode = slicer.mrmlScene.GetNodeByID(volNodeID)
    volName = volNode.GetStorageNode().GetFullNameFromFileName()
    volbasename = os.path.basename(volName)
    return volbasename
  #------------------------------------------------------------------------------
  def getNameVolumeNode(self,volNode):
    volName = volNode.GetStorageNode().GetFullNameFromFileName()
    volbasename = os.path.basename(volName)
    name = volbasename[:volbasename.find(".nii.gz")]
    return name

  #------------------------------------------------------------------------------
  def _saveMasks(self, nodes, folder, reader_name=None):

    for nodename, node in nodes.iteritems():
      try:
        segment_array = slicer.util.arrayFromSegment(node,node.GetSegmentation().GetNthSegmentID(0))
      except AttributeError as e:
        print (e)
        print ("Could Not Calculate Array For First Segment Because It's Empty --> Not Saving")
        segment_array = 0.0
      if np.mean(segment_array) == 0.0:
        pass
      else:
        masterVolumeNode = node.GetNodeReference(node.GetReferenceImageGeometryReferenceRole())
        print (nodename, node, masterVolumeNode)
        if masterVolumeNode is not None:
          name = masterVolumeNode.GetName()
        else:
          print ("PLEASE ADD THE CORRECT MASTER VOLUME TO AN EXTRA SEGMENT THAT WAS LOADED (LIKELY ADC_EQ_1)")
        # Add the readername if set
        if reader_name is not None:
          name += '_tumor_' + reader_name
        filename = os.path.join(folder, name)

        #Grab Segment IDs and Put Into VTK Array
        segmentation = node.GetSegmentation()
        segmentIds = vtk.vtkStringArray()
        segmentation.GetSegmentIDs(segmentIds)

        # Convert Segmentation to LabelMap
        labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')
        slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(node,segmentIds, labelmapVolumeNode, masterVolumeNode)

        # # Prevent overwriting existing files
        # if os.path.exists(filename + '.nii.gz'):
        #   self.logger.debug('Filename exists! Generating unique name...')
        #   idx = 1
        #   filename += '(%d).nii.gz'
        #   while os.path.exists(filename % idx):
        #     idx += 1
        #   filename = filename % idx
        # else:

        filename += '.nii.gz'
        # Save the node
        print ("About to save "+filename+" as label map from segment")
        slicer.util.saveNode(labelmapVolumeNode, filename)
        self.logger.info('Saved node %s in %s', labelmapVolumeNode.GetName(), filename)
                
    #------------------------------------------------------------------------------

      
