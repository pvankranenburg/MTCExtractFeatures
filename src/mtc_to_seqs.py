import music21 as m21
m21.humdrum.spineParser.flavors['JRP'] = True

import pandas as pd
import numpy as np
import json
import os
import argparse
from fractions import Fraction
from collections import defaultdict
from pathlib import Path
from itertools import zip_longest
from math import gcd
import subprocess
from subprocess import TimeoutExpired
import sys, traceback
import tempfile

from MTCFeatures.MTCFeatureLoader import MTCFeatureLoader

epsilon = 0.0001

# These paths must exist:
# ${mtcroot}/MTC-FS-INST-2.0/metadata
# ${mtcroot}/MTC-LC-1.0/metadata
# ${mtcroot}/MTC-ANN-2.0.1/metadata
# ${mtcroot}/MTC-FS-INST-2.0/krn
# ${mtcroot}/MTC-LC-1.0/krn
# ${mtcroot}/MTC-ANN-2.0.1/krn

parser = argparse.ArgumentParser(description='Convert MTC .krn to feature sequences')

### MTC
parser.add_argument(
    '-mtcfsinst',
    dest='gen_mtcfsinst',
    help='Generate sequences for MTC-FS-INST.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-mtcann',
    dest='gen_mtcann',
    help='Generate sequences for MTC-ANN.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-mtcroot',
    type=str,
    help='path to MTC to find metadata',
    default='/Users/Krane108/data/MTC/'
)
parser.add_argument(
    '-mtcanntextfeatspath',
    type=str,
    help='filename with text features for MTC-ANN',
    default='/Users/krane108/git/MTCExtractFeatures/src/mtcann_textfeatures.jsonl'
)
parser.add_argument(
    '-mtcfsinsttextfeatspath',
    type=str,
    help='filename with text features for MTC-FS-INST',
    default='/Users/krane108/git/MTCExtractFeatures/src/mtcfsinst_textfeatures.jsonl'
)

### ESSEN
parser.add_argument(
    '-essen',
    dest='gen_essen',
    help='Generate sequences for Essen collection.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-essenroot',
    type=str,
    help='path to essen data. ${essenroot}/allkrn, ${essenroot}/metadata.csv should exist',
    default='/Users/krane108/data/essen'
)

### BACH CHORALES
parser.add_argument(
    '-chorales',
    dest='gen_chorales',
    help='Generate sequences for Bach Chorales (melodies).',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-choraleroot',
    type=str,
    help='path to chorale data. ${choraleroot}/allkrn, ${choraleroot}/metadata.csv should exist',
    default='/Users/krane108/data/bachchorales'
)

### RISM INCIPITS
parser.add_argument(
    '-rism',
    dest='gen_rism',
    help='Generate sequences for Rism incipits.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-rismroot',
    type=str,
    help='path to rism data. ${rismroot}/rismmetadata.csv should exist',
    default='/Users/krane108/data/rism_incipits_230419'
)


### THE SESSION
parser.add_argument(
    '-thesession',
    dest='gen_thesession',
    help='Generate sequences for The Session corpus.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-thesessionroot',
    type=str,
    help='path to The Session data. ${thesessionroot}/krn_mono, ${thesessionroot}/ses_id2title.csv should exist',
    default='/Users/krane108/data/MELFeatures/thesession'
)

### KOLBERG
parser.add_argument(
    '-kolberg',
    dest='gen_kolberg',
    help='Generate sequences for the Kolberg Collection.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-kolbergroot',
    type=str,
    help='path to Kolberg data. ${kolbergroot}/krn, ${kolbergroot}/kb_id2title.csv should exist',
    default='/Users/krane108/data/MELFeatures/kolberg'
)

### CRE
parser.add_argument(
    '-cre',
    dest='gen_cre',
    help='Generate sequences for The Ceol Rince na hÉireann corpus.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-creroot',
    type=str,
    help='path to CRE data. ${creroot}/krn, ${cre}/cre_id2title.csv should exist',
    default='/Users/krane108/data/MELFeatures/cre'
)

### Eyck
parser.add_argument(
    '-eyck',
    dest='gen_eyck',
    help='Generate sequences for Fluyten Lusthof by Van Eyck.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-eyckroot',
    type=str,
    help='path to CRE data. ${creroot}/krn, ${cre}/metadata.csv should exist',
    default='/Users/krane108/data/MELFeatures/eyck'
)

### OUTPUTPATH
parser.add_argument(
    '-outputpath',
    type=str,
    help='Directory to put resulting .json or jsonl files in.',
    default='' # will be configured below
)

### STARTAT
parser.add_argument(
    '-startat',
    type=str,
    help='NLBID of the melody to start with. Skips all preceeding ones.',
    default=''
)

### ONLY
parser.add_argument(
    '-only',
    type=str,
    help='NLBID of the melody to process. Skips all other ones.',
    default=''
)

### STOPAT
parser.add_argument(
    '-stopat',
    type=str,
    help='NLBID of the melody to stop before (not inclusive). Skips all subsequent ones.',
    default=''
)

### MISSING
parser.add_argument(
    '-missing',
    help='Only generate missing .json files. Do not overwrite existing.',
    default=False,
    action='store_true'
)

args = parser.parse_args()

mtcfsroot = Path(args.mtcroot, 'MTC-FS-INST-2.0')
mtcannroot = Path(args.mtcroot, 'MTC-ANN-2.0.1')
mtclcroot = Path(args.mtcroot, 'MTC-LC-1.0')

mtcfskrndir = Path(args.mtcroot, 'MTC-FS-INST-2.0','krn')
mtcannkrndir = Path(args.mtcroot, 'MTC-ANN-2.0.1','krn')
mtclckrndir = Path(args.mtcroot, 'MTC-LC-1.0','krn')

essenroot = Path(args.essenroot)
essenkrndir = Path(args.essenroot, 'krn')
essenmetadatapath = Path(args.essenroot, 'metadata.csv')

choraleroot = Path(args.choraleroot)
choralekrndir = Path(args.choraleroot, 'allkrn')
choralemetadatapath = Path(args.choraleroot, 'metadata.csv')

thesessionroot = Path(args.thesessionroot)
thesessionkrndir = Path(args.thesessionroot, 'krn_mono_withkey')
thesessionmeatadatapath = Path(args.thesessionroot, 'ses_id2title.csv')

kolbergroot = Path(args.kolbergroot)
kolbergkrndir = Path(args.kolbergroot, 'krn')
kolbergmeatadatapath = Path(args.kolbergroot, 'kb_id2title.csv')

creroot = Path(args.creroot)
crekrndir = Path(args.creroot, 'krn_withkey')
cremetadatapath = Path(args.creroot, 'cre_id2title.csv')

rismroot = Path(args.rismroot)
rismkrndir = Path(args.rismroot, 'krn')
rismmetadatapath = Path(args.rismroot, 'metadata.csv')

eyckroot = Path(args.eyckroot)
eyckkrndir = Path(args.eyckroot, 'krn')
eyckmetadatapath = Path(args.eyckroot, 'metadata.csv')

mtcfsinsttextfeatspath = Path(args.mtcfsinsttextfeatspath)
mtcanntextfeatspath = Path(args.mtcanntextfeatspath)

outputpath = '' #will be overridden with Path object, below

if args.outputpath == '':
    #set default
    outputpath = tempfile.gettempdir()
    #check command line
    if args.gen_mtcann:
        outputpath = '.'
    if args.gen_mtcfsinst:
        outputpath = '.'
    if args.gen_essen:
        outputpath = os.path.join(essenroot, 'mtcjson')
    if args.gen_chorales:
        outputpath = '.'
    if args.gen_thesession:
        outputpath = os.path.join(thesessionroot, 'mtcjson')
    if args.gen_kolberg:
        outputpath = os.path.join(kolbergroot, 'mtcjson')
    if args.gen_cre:
        outputpath = os.path.join(creroot, 'mtcjson')
    if args.gen_rism:
        outputpath = os.path.join(rismroot, 'mtcjson')
    if args.gen_eyck:
        outputpath = os.path.join(eyckroot, 'mtcjson')
else: #outputpath provided at command line
    outputpath = args.outputpath


#these are indicated as 'vocal' in MTC-FS-INST-2.0 metadata, but are NOT
nlbids_notvocal = [
    'NLB179932_01',
    'NLB175861_01',
    'NLB175902_01',
    'NLB142256_01',
    'NLB179920_01',
    'NLB175873_01',
    'NLB175938_01',
    'NLB179916_01',
    'NLB175945_01',
    'NLB175826_01',
    'NLB175926_01',
    'NLB004881_01',
    'NLB004794_01',
    'NLB175934_01',
    'NLB175834_01',
    'NLB179867_01',
    'NLB004786_01',
    'NLB175849_01',
    'NLB004844_01',
    'NLB004839_01',
    'NLB175795_01',
    'NLB004827_01',
    'NLB004856_01',
    'NLB004848_01',
    'NLB004835_01',
    'NLB004860_01',
    'NLB004872_01',
    'NLB190125_01',
    'NLB004779_01',
    'NLB004911_01',
    'NLB004811_01',
    'NLB004837_01',
    'NLB004854_01',
    'NLB140072_02',
    'NLB004829_01',
    'NLB175797_01',
    'NLB004858_01',
    'NLB004825_01',
    'NLB004846_01',
    'NLB123127_01',
    'NLB004913_01',
    'NLB004813_01',
    'NLB004870_01',
    'NLB004901_01',
    'NLB004862_01',
    'NLB004777_01',
    'NLB130097_01',
    'NLB179922_01',
    'NLB004854_02',
    'NLB175871_01',
    'NLB179930_01',
    'NLB175863_01',
    'NLB175936_01',
    'NLB179918_01',
    'NLB004784_01',
    'NLB004891_01',
    'NLB175928_01',
    'NLB175924_01',
    'NLB004796_01',
    'NLB179914_01',
    'NLB179869_01',
    'NLB004788_01',
    'NLB004805_01',
    'NLB004905_01',
    'NLB150179_02',
    'NLB004878_01',
    'NLB004866_01',
    'NLB004917_01',
    'NLB004817_01',
    'NLB004909_01',
    'NLB004809_01',
    'NLB004874_01',
    'NLB004821_01',
    'NLB004842_01',
    'NLB004833_01',
    'NLB175894_01',
    'NLB004850_01',
    'NLB004887_01',
    'NLB004899_01',
    'NLB179910_01',
    'NLB004780_01',
    'NLB179861_01',
    'NLB004895_01',
    'NLB175932_01',
    'NLB175832_01',
    'NLB175804_01',
    'NLB141973_02',
    'NLB179934_01',
    'NLB134872_02',
    'NLB175875_01',
    'NLB179926_01',
    'NLB004850_02',
    'NLB175853_01',
    'NLB179863_01',
    'NLB004897_01',
    'NLB004782_01',
    'NLB175930_01',
    'NLB175830_01',
    'NLB175941_01',
    'NLB009297_01',
    'NLB179912_01',
    'NLB004885_01',
    'NLB004790_01',
    'NLB175922_01',
    'NLB175877_01',
    'NLB179924_01',
    'NLB004852_02',
    'NLB179936_01',
    'NLB179928_01',
    'NLB004876_01',
    'NLB004915_01',
    'NLB004815_01',
    'NLB004819_01',
    'NLB004864_01',
    'NLB179890_01',
    'NLB004907_01',
    'NLB004852_01',
    'NLB004831_01',
    'NLB175896_01',
    'NLB004840_01',
    'NLB004902_01',
    'NLB004861_01',
    'NLB004810_01',
    'NLB004910_01',
    'NLB004873_01',
    'NLB179887_01',
    'NLB004826_01',
    'NLB004838_01',
    'NLB004834_01',
    'NLB004849_01',
    'NLB004857_01',
    'NLB004880_01',
    'NLB179909_01',
    'NLB175944_01',
    'NLB175939_01',
    'NLB179917_01',
    'NLB004892_01',
    'NLB075947_02',
    'NLB175848_01',
    'NLB004787_01',
    'NLB175935_01',
    'NLB175856_01',
    'NLB004799_01',
    'NLB142453_01',
    'NLB142633_02',
    'NLB175803_01',
    'NLB179933_01',
    'NLB175872_01',
    'NLB179921_01',
    'NLB175854_01',
    'NLB179907_01',
    'NLB175829_01',
    'NLB004785_01',
    'NLB004890_01',
    'NLB175937_01',
    'NLB179919_01',
    'NLB179868_01',
    'NLB004789_01',
    'NLB175846_01',
    'NLB179915_01',
    'NLB004797_01',
    'NLB175858_01',
    'NLB004882_01',
    'NLB175925_01',
    'NLB175825_01',
    'NLB175870_01',
    'NLB179923_01',
    'NLB004871_01',
    'NLB179885_01',
    'NLB004812_01',
    'NLB004912_01',
    'NLB004863_01',
    'NLB004776_01',
    'NLB004900_01',
    'NLB179889_01',
    'NLB004828_01',
    'NLB004855_01',
    'NLB004836_01',
    'NLB004847_01',
    'NLB004824_01',
    'NLB179935_01',
    'NLB175866_01',
    'NLB175905_01',
    'NLB114131_01',
    'NLB175878_01',
    'NLB004851_02',
    'NLB175874_01',
    'NLB175942_01',
    'NLB004793_01',
    'NLB175933_01',
    'NLB004781_01',
    'NLB004894_01',
    'NLB179860_01',
    'NLB175899_01',
    'NLB004843_01',
    'NLB004820_01',
    'NLB004851_01',
    'NLB123757_01',
    'NLB133670_01',
    'NLB004832_01',
    'NLB004879_01',
    'NLB004904_01',
    'NLB004804_01',
    'NLB004875_01',
    'NLB126963_02',
    'NLB004816_01',
    'NLB004916_01',
    'NLB175897_01',
    'NLB004830_01',
    'NLB004853_01',
    'NLB004822_01',
    'NLB004841_01',
    'NLB004869_01',
    'NLB004814_01',
    'NLB004914_01',
    'NLB004877_01',
    'NLB004906_01',
    'NLB004806_01',
    'NLB004865_01',
    'NLB004818_01',
    'NLB004853_02',
    'NLB179925_01',
    'NLB175876_01',
    'NLB179929_01',
    'NLB179937_01',
    'NLB141970_02',
    'NLB175931_01',
    'NLB004783_01',
    'NLB175852_01',
    'NLB004888_01',
    'NLB175923_01',
    'NLB179870_01',
    'NLB004884_01',
    'NLB179913_01'
]

base402pitch_hewlett = {
    1:"C--",
    2:"C-",
    3:"C",
    4:"C#",
    5:"C##",
    6:"D---",
    7:"D--",
    8:"D-",
    9:"D",
    10:"D#",
    11:"D##",
    12:"E---",
    13:"E--",
    14:"E-",
    15:"E",
    16:"E#",
    17:"E##",
    18:"F--",
    19:"F-",
    20:"F",
    21:"F#",
    22:"F##",
    23:"unused",
    24:"G--",
    25:"G-",
    26:"G",
    27:"G#",
    28:"G##",
    29:"A---",
    30:"A--",
    31:"A-",
    32:"A",
    33:"A#",
    34:"A##",
    35:"B---",
    36:"B--",
    37:"B-",
    38:"B",
    39:"B#",
    40:"B##",
}

pitch2base40_hewlett = {v: k for k, v in base402pitch_hewlett.items()}
pitch2base40_sapp    = {v: k-1 for k, v in base402pitch_hewlett.items()}

#song has no meter
class NoMeterError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)
    
#parsing failed
class ParseError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

#nlbid not in cache
class CacheError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

#feature vector not of same length
class FeatLenghtError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

#No key information in **krn
class NoKeyError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

#No notes in **krn
class NoNotesError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

#No notes in **krn
class MelodyTooShorError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

#onsets2ima takes too long
class IMATimeoutError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

# add left padding to partial measure after repeat bar
def padSplittedBars(s):
    partIds = [part.id for part in s.parts] 
    for partId in partIds: 
        measures = list(s.parts[partId].getElementsByClass('Measure')) 
        for m in zip(measures,measures[1:]): 
            if m[0].quarterLength + m[0].paddingLeft + m[1].quarterLength == m[0].barDuration.quarterLength: 
                m[1].paddingLeft = m[0].quarterLength 
    return s

# replace a chord with the highest note in the chord
def replaceChord(s):
    #trick: just add a pitch attribute to the Chord object
    for n in s.flat.getElementsByClass('Chord'):
        c = n.sortAscending()
        n.pitch = c.pitches[-1]
    return s

def parseMelody(path):
    try:
        s = m21.converter.parse(path)
    except m21.converter.ConverterException:
        raise ParseError(path)
    #add padding to partial measure caused by repeat bar in middle of measure
    s = padSplittedBars(s)
    s_noties = s.stripTies()
    m = s_noties.flat
    removeGrace(m)
    replaceChord(m)
    notes = list(m.flat.notes.stream())
    if len(notes) == 0:
        raise NoNotesError("")
    return m

# s : flat music21 stream without ties and without grace notes
def removeGrace(s):
    ixs = [s.index(n) for n in s.notes if n.quarterLength == 0.0]
    for ix in reversed(ixs):
        s.pop(ix)
    return s

# n: Note
# t: Pitch (tonic)
def pitch2scaledegree(n, t):
    tonicshift = t.diatonicNoteNum % 7
    return ( n.pitch.diatonicNoteNum - tonicshift ) % 7 + 1

# expect tonic in zeroth (or other very low) octave
def pitch2scaledegreeSpecifer(n, t):
    interval = m21.interval.Interval(noteStart=t, noteEnd=n)
    return m21.interval.prefixSpecs[interval.specifier]

# Tonic in 0-octave has value 0
def pitch2diatonicPitch(n, t):
    tonicshift = t.diatonicNoteNum % 7
    if tonicshift == 0:
        tonicshift = 7
    return ( n.pitch.diatonicNoteNum - tonicshift )

# Tonic in 0-octave has value 0
def pitch2diatonicPitch12(n, t):
    tonicshift = t.pitch.midi % 12
    return ( n.pitch.midi - tonicshift )

# Tonic in 0-octave has value 0
def pitch2diatonicPitch40(n, t):
    tonicshift = pitch2base40_sapp[t.pitch.name]
    return ( pitch2base40_sapp[n.pitch.name] + 40*n.octave - tonicshift)

# s : flat music21 stream without ties and without grace notes
def hasmeter(s):
    #no time signature at all
    if not s.getElementsByClass('TimeSignature'): return False
    #maybe it is an Essen song with Mixed meter.
    #---> that has meter!
    #mixedmetercomments = [c.comment for c in s.getElementsByClass('GlobalComment') if c.comment.startswith('Mixed meters:')]
    #if len(mixedmetercomments) > 0:
    #    return False
    return True

def notes2metriccontour(n1, n2):
    if n1.beatStrength > n2.beatStrength: return '-'
    if n1.beatStrength < n2.beatStrength: return '+'
    return '='

# s : flat music21 stream without ties and without grace notes
def m21TObeatstrength(s):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    return [n.beatStrength for n in s.notes]
 
# s : flat music21 stream without ties and without grace notes
def m21TOmetriccontour(s):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    metriccontour = [notes2metriccontour(x[0], x[1]) for x in zip(s.notes,s.notes[1:])]
    metriccontour.insert(0,None)
    return metriccontour

def getTonic(s):
    tonics = list(s.flat.getElementsByClass('Key'))
    if len(tonics) == 0:
        raise NoKeyError(str(s.metadata.filePath))
    else:
        tonic = s.flat.getElementsByClass('Key')[0].tonic
    return tonic

# s : flat music21 stream without ties and without grace notes
def m21TOscaledegrees(s):
    try:
        tonic = getTonic(s)
    except NoKeyError as e:
        print("No Key in ", e)
        return [None for x in s.notes]
    scaledegrees = [pitch2scaledegree(x, tonic) for x in s.notes]
    return scaledegrees

# s : flat music21 stream without ties and without grace notes
def m21TOChromaticScaleDegree(s):
    try:
        tonic = getTonic(s)
    except NoKeyError as e:
        print("No Key in ", e)
        return [None for x in s.notes]
    miditonic = tonic.midi % 12
    scaledegrees12 = [(n.pitch.midi - miditonic) % 12 + 1 for n in s.notes]
    return scaledegrees12

# s : flat music21 stream without ties and without grace notes
# output: M: major, m: minor, P: perfect, A: augmented, d: diminished
def m21TOscaleSpecifiers(s):
    try:
        tonic = getTonic(s)
    except NoKeyError as e:
        print("No Key in ", e)
        return [None for x in s.notes]
    #put A COPY of the tonic in 0th octave
    lowtonic = m21.note.Note(tonic.name)
    lowtonic.octave = 0
    return [pitch2scaledegreeSpecifer(x, lowtonic) for x in s.notes] 

# s : flat music21 stream without ties and without grace notes
# Tonic in 0-octave has value 0
def m21TOdiatonicPitches(s):
    try:
        tonic = getTonic(s)
    except NoKeyError as e:
        print("No Key in ", e)
        return [None for x in s.notes]
    scaledegrees = [pitch2diatonicPitch(x, tonic) for x in s.notes]
    return scaledegrees

# s : flat music21 stream without ties and without grace notes
# Tonic in 0-octave has value 0
def m21TOdiatonicPitches12(s):
    try:
        tonic = getTonic(s)
    except NoKeyError as e:
        print("No Key in ", e)
        return [None for x in s.notes]
    scaledegrees = [pitch2diatonicPitch12(x, tonic) for x in s.notes]
    return scaledegrees

# s : flat music21 stream without ties and without grace notes
# Tonic in 0-octave has value 0
def m21TOdiatonicPitches40(s):
    try:
        tonic = getTonic(s)
    except NoKeyError as e:
        print("No Key in ", e)
        return [None for x in s.notes]
    scaledegrees = [pitch2diatonicPitch40(x, tonic) for x in s.notes]
    return scaledegrees


# s : flat music21 stream without ties and without grace notes
def toDiatonicIntervals(s):
    return [None] + [n[1].pitch.diatonicNoteNum - n[0].pitch.diatonicNoteNum for n in zip(s.notes, s.notes[1:]) ]

# s : flat music21 stream without ties and without grace notes
def toChromaticIntervals(s):
    return [None] + [n[1].pitch.midi - n[0].pitch.midi for n in zip(s.notes, s.notes[1:]) ]

# compute expectancy of the note modelled with pitch proximity (Schellenberg, 1997)
def getPitchProximity(chromaticinterval):
    return [None, None] + [abs(c) if abs(c) < 12 else None for c in chromaticinterval[2:] ]

# compute expectancy of the realized note modelled with pitch reversal (Schellenberg, 1997)
def getOnePitchReversal(implicative, realized):
    if abs(implicative) == 6 or abs(implicative) > 11 or abs(realized) > 12:
        return None
    
    pitchrev_dir = None
    if abs(implicative) < 6:
        pitchrev_dir = 0
    if abs(implicative) > 6 and abs(implicative) < 12:
        if realized * implicative <= 0:
            pitchrev_dir = 1
        else:
            pitchrev_dir = -1
    
    pitchrev_ret = 1.5 if ( (abs(realized)>0) and (realized*implicative < 0) and (abs(implicative+realized) <= 2) ) else 0

    return pitchrev_dir + pitchrev_ret

# compute expectancies of the note modelled with pitch reversal (Schellenberg, 1997)
def getPitchReversal(chromaticinterval):
    return [None, None] + [getOnePitchReversal(i, r) for i,r in zip(chromaticinterval[1:], chromaticinterval[2:])] 

#compute boundary strength for the potential boundary FOLLOWING the note. Take durations from input
#duration of the rest following the note (normalized; whole note is 1.0) and maximized (1.0).
def getFranklandGPR2a(restduration):
    return [ min(1.0, float(Fraction(r) / 4.0)) if r is not None else None for r in restduration]

def getOneFranklandGPR2b(n1,n2,n3,n4):
    return ( 1.0 - (float(n1+n3)/(2.0*n2)) ) if (n2>n3) and (n2>n1) else None

#compute boundary strength for the potential boundary FOLLOWING the note.
#For the rule to apply, n2 must be longer than both n1 and n3. In addition
#n1 through n4 must be notes (not rests)
def getFranklandGPR2b(lengths, restdurations):
    #only applicable to melodies of length > 4
    if len(lengths) < 4:
        return [None] * len(lengths)
    quads = zip(lengths,lengths[1:],lengths[2:],lengths[3:])
    res =  [None] + [getOneFranklandGPR2b(n1, n2, n3, n4) for n1, n2, n3, n4 in quads] + [None, None]
    
    #check conditions (Frankland 2004, p.505): no rests in between, n2>n1 and n2>n3 (in getOneFranklandGPR2b())
    #rest_maks: positions with False result in None in res
    rest_present = [Fraction(r)>Fraction(0) if r is not None else False for r in restdurations]
    triple_rest_present = zip(rest_present,rest_present[1:],rest_present[2:])
    rest_mask = [False] + [not (r1 or r2 or r3) for r1, r2, r3 in triple_rest_present] + [False]
    #now set all values in res to None if False in mask
    res = [res[ix] if rest_mask[ix] else None for ix in range(len(res))]
    return res
    

def getOneFranklandGPR3a(n1, n2, n3, n4):
    if n2 != n3 and abs(n2-n3) > abs(n1-n2) and abs(n2-n3) > abs(n3-n4):
        return 1.0 - ( float(abs(n1-n2)+abs(n3-n4)) / float(2.0 * abs(n2-n3)) )
    else:
        return None

#The rule applies only if the transition from n2 to n3 is greater than from n1 to n2
#and from n3 to n4. In addition, the transition from n2 to n3 must be nonzero
def getFranklandGPR3a(midipitch):
    #only applicable to melodies of length > 4
    if len(midipitch) < 4:
        return [None] * len(midipitch)
    quads = zip(midipitch,midipitch[1:],midipitch[2:],midipitch[3:])
    return  [None] + [getOneFranklandGPR3a(n1, n2, n3, n4) for n1, n2, n3, n4 in quads] + [None, None]

def getOneFranklandGPR3d(n1,n2,n3, n4):
    if n1 != n2 or n3 != n4:
        return None
    if n3 > n1:
        return 1.0 - (float(n1)/float(n3))
    else:
        return 1.0 - (float(n3)/float(n1))

#... to apply, the length of n1 must equal n2, and the length of n3 must euqal n4
def getFranklandGPR3d(lengths):
    #only applicable to melodies of length > 4
    if len(lengths) < 4:
        return [None] * len(lengths)
    quads = zip(lengths,lengths[1:],lengths[2:],lengths[3:])
    return [None] + [getOneFranklandGPR3d(n1, n2, n3, n4) for n1, n2, n3, n4 in quads] + [None, None]
    #condition checking in getOneFranklandGRP3d()

#For LBDM parameters:
#Take interval AFTER note
#r1 is degree of change of interval AFTER the note
#compute boundary strength of interval FOLLOWING note
#note:       n0    n1    n2    n3    n4    n5
#            |  \  |  \  |  \  |  \  |  \
#interval    i0    i1    i2    i3    i4    i5
#            |  \  |  \  |  \  |  \  |  \  | 
#change      None  r1    r2    r3    r4    r5
#                  |  /  |  /  |  /  |  /  |  /
#strength    None  s1    s2    s3    s4    s5
#
#  s1 is computed from r1 and r2
#  s2 is computed from r2 and r3
# etc.

def getOneDegreeChange(x1, x2, const_add=0.0):
    res = None
    x1 += const_add
    x2 += const_add
    if x1 == x2: return 0.0
    if (x1+x2) != 0 and x1 >= 0 and x2 >= 0:
        res = float(abs(x1-x2)) / float (x1 + x2)
    return res

#Cambouropoulos 2001
def getDegreeChangeLBDMpitch(chromaticinterval, threshold=12, const_add=1):
    #for lbdm we need at least 3 notes
    if len(chromaticinterval) < 3:
        return [None] * len(chromaticinterval)
    # we need absolute values
    # and thr_int <= threshold
    # and shift such that chormaticinterval is interval FOLLOWING note
    thr_int = [min(threshold,abs(i)) for i in chromaticinterval[1:]] + [None] 
    pairs = zip(thr_int[:-1],thr_int[1:-1])
    rpitch = [None] + [getOneDegreeChange(x1, x2, const_add=const_add) for x1, x2 in pairs] + [None]
    return rpitch

#Cambouropoulos 2001
#default threshold: whole note (4.0 quarterLength)
def getDegreeChangeLBDMioi(ioi, threshold=4.0):
    #for lbdm we need at least 3 notes
    if len(ioi) < 3:
        return [None] * len(ioi)
    #We need IOI AFTER the note, and we need maximize the value
    thr_ioi = [min(threshold,i) for i in ioi[:-1]] + [None]
    pairs = zip(thr_ioi[:-1],thr_ioi[1:-1])
    rioi = [None] + [getOneDegreeChange(x1, x2) for x1, x2 in pairs ] + [None]
    return rioi
    
#Cambouropoulos 2001
def getDegreeChangeLBDMrest(restduration_frac, threshold=4.0):
    #for lbdm we need at least 3 notes
    if len(restduration_frac) < 3:
        return [None] * len(restduration_frac)
    #need rest AFTER note, and apply threshold
    thr_rd = [min(threshold, float(Fraction(r))) if r is not None else 0.0 for r in restduration_frac[:-1]] + [None]
    pairs = zip(thr_rd[:-1], thr_rd[1:-1])
    rrest = [None] + [getOneDegreeChange(x1, x2) for x1, x2 in pairs] + [None]
    return rrest

#Boundary strength AFTER the note
def getBoundaryStrength(rs, intervals):
    #print(list(zip(rs, intervals)))
    pairs = zip(rs[1:-1], rs[2:-1], intervals[1:])
    strength = [ c * (r1 + r2) for r1, r2, c in pairs]
    #very shor melodies:
    if len(strength) == 0:
        return [None, None, None]
    #normalize
    maxspitch = max(strength)
    if maxspitch > 0:
        strength = [s / maxspitch for s in strength]
    #Add first and last
    strength = [None] + strength + [None, None]
    return strength
    
def getBoundaryStrengthPitch(rpitch, chromaticinterval, threshold=12):
    #for lbdm we need at least 3 notes
    if len(chromaticinterval) < 3:
        return [None] * len(chromaticinterval)
    # we need absolute values
    # and thr_int <= threshold
    # and shift such that chormaticinterval is interval FOLLOWING note
    thr_int = [min(threshold,abs(i)) for i in chromaticinterval[1:]] + [None] 
    return getBoundaryStrength(rpitch, thr_int)

def getBoundaryStrengthIOI(rioi, ioi, threshold=4.0):
    #for lbdm we need at least 3 notes
    if len(ioi) < 3:
        return [None] * len(ioi)
    #We need IOI AFTER the note, and we need maximize the value
    thr_ioi = [min(threshold,i) for i in ioi[:-1]] + [None]
    return getBoundaryStrength(rioi, thr_ioi)

def getBoundaryStrengthRest(rrest, restduration_frac, threshold=4.0):
    #for lbdm we need at least 3 notes
    if len(restduration_frac) < 3:
        return [None] * len(restduration_frac)
    #need rest AFTER note, and apply threshold
    thr_rd = [min(threshold, float(Fraction(r))) if r is not None else 0.0 for r in restduration_frac[:-1]] + [None]
    return getBoundaryStrength(rrest, thr_rd)

#Cambouropoulos 2001
#Gives strength fot boundary AFTER the note
def getLocalBoundaryStrength(spitch, sioi, srest):
    #for lbdm we need at least 3 notes
    if len(spitch) < 3:
        return [None] * len(spitch)
    triplets = zip(spitch[1:-2], sioi[1:-2], srest[1:-2]) #remove None values at begin and end
    strength = [0.25*p + 0.5*i + 0.25*r for p, i, r in triplets]
    strength = [None] + strength + [None, None]
    return strength

# s : flat music21 stream without ties and without grace notes
def m21TOPitches(s):
    return [n.pitch.nameWithOctave for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TOMidiPitch(s):
    return [n.pitch.midi for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TODuration(s):
    return [float(n.duration.quarterLength) for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TODuration_fullname(s):
    return [n.duration.fullName for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TODuration_frac(s):
    return [str(Fraction(n.duration.quarterLength)) for n in s.notes]

def getDurationcontour(duration_frac):
    return [None] + ['-' if Fraction(d2)<Fraction(d1) else '+' if Fraction(d2)>Fraction(d1) else '=' for d1, d2 in zip(duration_frac,duration_frac[1:])]

# s : flat music21 stream without ties and without grace notes
def m21TONextIsRest(s):
    notesandrests = list(s.notesAndRests)
    nextisrest = [ nextnote.isRest for note, nextnote in zip(notesandrests, notesandrests[1:]) if note.isNote or note.isChord]
    if notesandrests[-1].isNote or notesandrests[-1].isChord:
        nextisrest.append(None) #final note
    return nextisrest

#Duration of the rest(s) FOLLOWING the note
def m21TORestDuration_frac(s):
    restdurations = []
    notesandrests = list(s.notesAndRests)
    rest_duration = Fraction(0)
    #this computes length of rests PRECEEDING the note
    for event in notesandrests:
        if event.isRest:
            rest_duration += Fraction(event.duration.quarterLength)
        if event.isNote or event.isChord:
            if rest_duration == 0:
                restdurations.append(None)
            else:
                restdurations.append(str(rest_duration))
            rest_duration = Fraction(0)
    #shift list and add last
    if notesandrests[-1].isNote or notesandrests[-1].isChord:
        restdurations = restdurations[1:] + [None]
    else:
        restdurations = restdurations[1:] + [str(rest_duration)]
    return restdurations

# s : flat music21 stream without ties and without grace notes
def m21TOTimeSignature(s):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    return [n.getContextByClass('TimeSignature').ratioString for n in s.notes]

def m21TOKey(s):
    try:
        getTonic(s)
        keys =  [(k.tonic.name, k.mode) for k in [n.getContextByClass('Key') for n in s.notes]]
    except NoKeyError as e:
        print("No Key in ", e)
        keys = [(None, None) for n in s.notes]
    return list(zip(*keys))

# "4" -> ('4', '0')
# "3 1/3" -> ('3', '1/3')
def beatStrTOtuple(bstr):
    bstr_splitted = bstr.split(' ')
    if len(bstr_splitted) == 1:
        bstr_splitted.append('0')
    return bstr_splitted[0], bstr_splitted[1]

# s : flat music21 stream without ties and without grace notes
def m21TOBeat_str(s):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    beats = []
    beat_fractions = []
    for n in s.notes:
        try:
            b, bfr = beatStrTOtuple(n.beatStr)
        except m21.base.Music21ObjectException: #no time signature
            b, bfr = '0', '0'
        beats.append(b)
        beat_fractions.append(bfr)
    return beats, beat_fractions

# s : flat music21 stream without ties and without grace notes
def m21TOBeat_float(s):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    beats = []
    for n in s.notes:
        try:
            beat_float = float(n.beat)
        except m21.base.Music21ObjectException: #no time signature
            beat_float = 0.0
        beats.append(beat_float)
    return beats

# s : flat music21 stream without ties and without grace notes, and with left padding for partial measures
# caveat: upbeat before meter change is interpreted in context of old meter.
# origin is first downbeat in each phrase
def m21TOBeatInSongANDPhrase(s, phrasepos):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    phrasestart_ixs = [ix+1 for ix, pp in enumerate(zip(phrasepos,phrasepos[1:])) if pp[1] < pp[0] ]
    #print(phrasestart_ixs)
    startbeat = Fraction(s.notesAndRests[0].beat)
    if startbeat != Fraction(1):  #upbeat
        startbeat = Fraction(-1 * s.notesAndRests[0].getContextByClass('TimeSignature').beatCount) + startbeat
    startbeat = startbeat - Fraction(1) #shift origin to first first (no typo) beat in measure
    #print('startbeat', startbeat)
    #beatfraction: length of the note with length of the beat as unit
    beatinsong, beatinphrase, beatfraction = [], [], []
    n_first = s.notesAndRests[0]
    if n_first.isNote or n_first.isChord:
        beatinsong.append(startbeat)
        beatinphrase.append(startbeat)
        duration_beatfraction = Fraction(n_first.duration.quarterLength) / Fraction(n_first.beatDuration.quarterLength)
        beatfraction.append(duration_beatfraction) # add first note here, use nextnote in loop
    cumsum_beat_song = startbeat
    cumsum_beat_phrase = startbeat
    note_ix = 0
    notesandrests = list(s.notesAndRests)
    for n, nextnote in zip(notesandrests, notesandrests[1:]):
        #print("--------------")
        #print(n)
        duration_beatfraction = Fraction(n.duration.quarterLength) / Fraction(n.beatDuration.quarterLength)
        cumsum_beat_song += duration_beatfraction
        cumsum_beat_phrase += duration_beatfraction
        #print(cumsum_beat_song)
        if n.isNote or n.isChord:
            if note_ix in phrasestart_ixs:
                cumsum_beat_phrase = Fraction(n.beat)
                #print('beat ', cumsum_beat_phrase)
                if cumsum_beat_phrase != Fraction(1): #upbeat
                    cumsum_beat_phrase = Fraction(-1 * n.getContextByClass('TimeSignature').beatCount) + cumsum_beat_phrase
                cumsum_beat_phrase = cumsum_beat_phrase - Fraction(1)
                #print(note_ix, n, cumsum_beat_phrase)
                beatinphrase[-1] = cumsum_beat_phrase
                cumsum_beat_phrase += duration_beatfraction
            #print(f'{n}, beat: {Fraction(n.beat)}, fraction: {duration_beatfraction}')
            #print("note: ", cumsum_beat_song)
            note_ix += 1
        if nextnote.isNote or nextnote.isChord:
            beatinphrase.append(cumsum_beat_phrase)
            beatinsong.append(cumsum_beat_song)
            duration_beatfraction = Fraction(nextnote.duration.quarterLength) / Fraction(nextnote.beatDuration.quarterLength)
            beatfraction.append(duration_beatfraction)
    beatinsong = [str(f) for f in beatinsong] #string representation to make it JSON serializable
    beatinphrase = [str(f) for f in beatinphrase] #string representation to make it JSON serializable
    beatfraction = [str(f) for f in beatfraction] #string representation to make it JSON serializable
    return beatinsong, beatinphrase, beatfraction

#origin is onset of last! beat in each phrase
#TODO: what if note on last beat is tied with previous? Syncope.
def getBeatinphrase_end(beatinphrase, phrase_ix, beat):
    #find offset per phrase
    beatinphrase_end = []
    origin = defaultdict(lambda: 0.0)
    for ix in range(len(beatinphrase)):
        if abs(beat[ix] - 1.0) < epsilon:
            origin[phrase_ix[ix]] = Fraction(beatinphrase[ix])
    for ix in range(len(beatinphrase)):
        beatinphrase_end.append( Fraction(beatinphrase[ix]) - Fraction(origin[phrase_ix[ix]]) )
    return [str(f) for f in beatinphrase_end]

def value2contour(ima1, ima2):
    if ima1 > ima2: return '-'
    if ima1 < ima2: return '+'
    return '='

def getFromJson(nlbid, path, feature, totype=int):
    with open( path+'/'+nlbid+'.json', 'r') as f:
        song = json.load(f)
    featvals = [totype(x[feature]) for x in song[nlbid]['symbols']]
    return featvals

def getIMA(s, onsets):
    """returns IMA and IMASPECT weights. Commandline onsets2ima must be installed."""
    s = s.stripTies()

    # with subprocess.Popen(["onsets2ima","-onsets"] + [str(o) for o in onsets], stdout=subprocess.PIPE) as proc:
    #     output = proc.stdout.read().decode('ascii')

    proc = subprocess.Popen(["onsets2ima","-onsets"] + [str(o) for o in onsets], stdout=subprocess.PIPE)
    try:
        outs, errs = proc.communicate(timeout=5)
    except TimeoutExpired:
        proc.kill()
        raise IMATimeoutError
    output = outs.decode('ascii')

    ima_str = output.split('\n')[0].strip()
    ima_spect_str = output.split('\n')[1].strip()

    ima = [float(w) for w in ima_str.split(' ')]
    ima_spect = [float(w) for w in ima_spect_str.split(' ')]

    #if onset of first note != 0 (start with rest), add zeros to ima_spect
    ima_spect = [0.0]*onsets[0] + ima_spect

    ima_spect = [ima_spect[o] for o in onsets]

    return ima, ima_spect

def getPhraseInfo(s):
    lineoffsets = [Fraction(0,1)]
    for cmt in s.flat.getElementsByClass(m21.humdrum.spineParser.GlobalComment):
        if cmt.offset > 1e-4: #first already added
            if "segment" in cmt.comment or "linebreak:original" in cmt.comment:
                lineoffsets.append(Fraction(cmt.offset))
    lineends = lineoffsets[1:] + [Fraction(s.flat.notesAndRests.last().offset) + Fraction(s.flat.notesAndRests.last().quarterLength)]

    offsetsfinalnotes = []
    for ix, off in enumerate(lineends):
        n = s.flat.notes.stream().getElementBeforeOffset(off)
        if n == None: #There is no Note. Probably a first phrase with only rests...
            offsetsfinalnotes.append(lineoffsets[ix]) #add start of phrase. Results in phrase of length 0.
        else:
            offsetsfinalnotes.append(Fraction(n.offset)) 

    phraselengths = [offsetsfinalnotes[i] - lineoffsets[i] for i in range(len(lineoffsets))]

    phraseixs = []
    curphr = 0
    for n in s.flat.notes:
        if n.offset>=lineends[curphr]:
            curphr += 1
        phraseixs.append(curphr)

    phrasepos = []
    for ix, n in enumerate(s.flat.notes):
        phrlen = phraselengths[phraseixs[ix]]
        if phrlen == 0:
            #What if a phrase has length 0 (if only one note is in the phrase)?
            phroffset = 0.0
        else:
            phroffset = (n.offset - lineoffsets[phraseixs[ix]]) / phraselengths[phraseixs[ix]]
        phrasepos.append(float(phroffset))

    return phraseixs, phrasepos

def getSongPos(onsettick):
    onsets = np.array(onsettick)
    return list(onsets / onsets[-1])

def getPhraseEnd(phrasepos):
    return [x[1]<x[0] for x in zip(phrasepos, phrasepos[1:])] + [True]

#defined here: http://www.ccarh.org/publications/reprints/base40/
#Cbb = 1, middle C is octave 3
def getPitch40_Hewlett(s):
    return [pitch2base40_hewlett[n.pitch.name] + 40*(n.octave - 1) for n in s.notes]

#defined here: https://wiki.ccarh.org/wiki/Base_40
#Cbb = 0, middle C is octave 4
def getPitch40_Sapp(s):
    return [pitch2base40_sapp[n.pitch.name] + 40*(n.octave) for n in s.notes]

def getOctave(s):
    return [n.octave for n in s.notes]

def getContour3(midipitch1, midipitch2):
    if midipitch1 > midipitch2 : return '-'
    if midipitch1 < midipitch2 : return '+'
    return '='

def getContour5(midipitch1, midipitch2, thresh):
    diff = midipitch2 - midipitch1
    if   diff >= thresh : return '++'
    elif diff > 0 : return '+'
    elif diff == 0 : return '='
    elif diff <= -thresh : return '--'
    elif diff < 0 : return '-'

def midipitch2contour3(mp, undef=None):
    return [undef] + [getContour3(p[0], p[1]) for p in zip(mp,mp[1:])]

def midipitch2contour5(mp, thresh=3, undef=None):
    return [undef] + [getContour5(p[0], p[1], thresh) for p in zip(mp,mp[1:])]

def getIOR_frac(ioi_frac):
    return [None] + [str(Fraction(ioi2)/Fraction(ioi1)) if ioi1 is not None and ioi2 is not None else None for ioi1, ioi2 in zip(ioi_frac,ioi_frac[1:])]

def getIOR(ior_frac):
    return [float(Fraction(i)) if i is not None else None for i in ior_frac]

#IOI in quarterLength
#last note: take duration
def getIOI(ioi_frac):
    return [float(Fraction(i)) if i is not None else None for i in ioi_frac]

#last should be none
def getIOI_frac(duration_frac, restduration_frac):
    res =  [str(Fraction(d)+Fraction(r)) if r is not None else str(Fraction(d)) for d, r, in zip(duration_frac[:-1], restduration_frac[:-1])]
    #check last item. If no rest follows, we cannot compute IOI
    if restduration_frac[-1] is not None:
        res = res + [ str( Fraction(duration_frac[-1])+Fraction(restduration_frac[-1]) ) ]
    else:
        res = res + [None]
    return res

def lcm(a, b):
    """Computes the lowest common multiple."""
    return a * b // gcd(a, b)

def fraction_gcd(x, y):
    """Computes the greatest common divisor as Fraction"""
    a = x.numerator
    b = x.denominator
    c = y.numerator
    d = y.denominator
    return Fraction(gcd(a, c), lcm(b, d))

def getDurationUnit(s):
    sf = s.flat.notesAndRests
    unit = Fraction(sf[0].duration.quarterLength)
    for n in sf:
        unit = fraction_gcd(unit, Fraction(n.duration.quarterLength))
    return fraction_gcd(unit, Fraction(1,1)) # make sure 1 is dividable by the unit.denominator

def getResolution(s) -> int:
    """Return the number of ticks per quarter note given the duration unit."""
    unit = getDurationUnit(s)
    #number of ticks is 1 / unit (if that is an integer)
    ticksPerQuarter = unit.denominator / unit.numerator
    if ticksPerQuarter.is_integer():
        return int(unit.denominator / unit.numerator)
    else:
        print(s.filePath, ' non integer number of ticks per Quarter')
        return 0

def getOnsetTick(s):
    """Returns a list of onsets (ints). Onsets are multiples of the duration unit."""
    ticksPerQuarter = getResolution(s)
    onsets = [int(n.offset * ticksPerQuarter) for n in s.flat.notes]
    return onsets

def getIMAcontour(ima):
    imacontour = [value2contour(ima[0], ima[1]) for ima in zip(ima,ima[1:])]
    imacontour.insert(0,None)
    return imacontour

#returns:
#- lyrics
#- noncontentword
#- wordend
#- phoneme
#- rhymes
#- rhymescontentwords
#- wordstress
#- melismastate
class GetTextFeatures():
    def __init__(self):
        self.seqs = {}
    def addSeqsFromFile(self, filename):
        _seqs = MTCFeatureLoader(filename).sequences()
        #convert to dict
        _seqs = {seq['id']: seq for seq in _seqs}
        #add to cache
        self.seqs[filename] = _seqs
    def __call__(self, nlbid, filename):
        if not filename in self.seqs.keys():
            self.addSeqsFromFile(filename)
        if not nlbid in self.seqs[filename].keys():
            raise CacheError(nlbid)
        return (
            self.seqs[filename][nlbid]['features']['lyrics'],
            self.seqs[filename][nlbid]['features']['noncontentword'],
            self.seqs[filename][nlbid]['features']['wordend'],
            self.seqs[filename][nlbid]['features']['phoneme'],
            self.seqs[filename][nlbid]['features']['rhymes'],
            self.seqs[filename][nlbid]['features']['rhymescontentwords'],
            self.seqs[filename][nlbid]['features']['wordstress'],
            self.seqs[filename][nlbid]['features']['melismastate']
        )
getTextFeatures = GetTextFeatures()

#Generate the sequences
#iterator
#song ids should be in index of song_metadata
def getSequences(
        krndir,
        song_metadata,
        source_metadata,
        textFeatureFile=None,
        fieldmap={'TuneFamily':'TuneFamily', 'TuneFamily_full' : 'TuneFamily'},
        startat=None,
        stopat=None,
        only=None,
        missing=False, #True: only generate missing 
    ):

    id_list = song_metadata.index

    seen=False
    for nlbid in id_list:
        if startat:
            if nlbid==startat:
                seen=True
            if not seen:
                continue
        if only:
            if nlbid != only:
                continue

        if stopat:
            if nlbid==stopat:
                break
        
        print(nlbid)
        
        #construct filename
        #rep might have subdirectories (e.g. rism)
        if 'filename' in song_metadata.columns:
            filename = song_metadata.loc[nlbid,'filename']
        else:
            filename = nlbid+'.krn'

        if missing:
            jsonfilename = filename.replace('.krn', '.json')
            if os.path.isfile(os.path.join(outputpath, jsonfilename)):
                print (f"{jsonfilename} exists. Skipping.")
                continue

        try:
            s = parseMelody(os.path.join(krndir, filename))
        except ParseError:
            print(nlbid, "does not exist")
            continue
        except NoNotesError:
            print(nlbid, "has not notes.")
            continue
        except Exception:
            print("Exception in user code:")
            print("-"*60)
            traceback.print_exc(file=sys.stdout)
            print("-"*60)
            continue

        if len(s.flat.notes) < 2:
            print(f"{nlbid}: Melody too short ({len(s.flat.notes)} notes)")
            continue

        try:
            diatonicPitches = m21TOdiatonicPitches(s)
            diatonicPitches12 = m21TOdiatonicPitches12(s)
            diatonicPitches40 = m21TOdiatonicPitches40(s)
            diatonicinterval = toDiatonicIntervals(s)
            chromaticinterval = toChromaticIntervals(s)
            pitch = m21TOPitches(s)
            pitch40_hewlett = getPitch40_Hewlett(s)
            pitch40_sapp = getPitch40_Sapp(s)
            octave = getOctave(s)
            midipitch = m21TOMidiPitch(s)
            sd = m21TOscaledegrees(s)
            sdspec = m21TOscaleSpecifiers(s)
            chr_sd = m21TOChromaticScaleDegree(s)
            pitchproximity = getPitchProximity(chromaticinterval)
            pitchreversal = getPitchReversal(chromaticinterval)
            nextisrest = m21TONextIsRest(s)
            restduration_frac = m21TORestDuration_frac(s)
            tonic, mode = m21TOKey(s)
            contour3 = midipitch2contour3(midipitch)
            contour5 = midipitch2contour5(midipitch, thresh=3)
            duration = m21TODuration(s)
            duration_fullname = m21TODuration_fullname(s)
            duration_frac = m21TODuration_frac(s)
            durationcontour = getDurationcontour(duration_frac)
            onsettick = getOnsetTick(s)
            ima, ima_spect = getIMA(s, onsettick)
            ic = getIMAcontour(ima)
            phrase_ix, phrasepos = getPhraseInfo(s)
            phrase_end = getPhraseEnd(phrasepos)
            ioi_frac = getIOI_frac(duration_frac, restduration_frac)
            ioi = getIOI(ioi_frac)
            ior_frac = getIOR_frac(ioi_frac)
            ior = getIOR(ior_frac)
            songpos = getSongPos(onsettick)
            gpr2a_Frankland = getFranklandGPR2a(restduration_frac)
            gpr2b_Frankland = getFranklandGPR2b(duration, restduration_frac) #or use IOI and no rest check!!!
            gpr3a_Frankland = getFranklandGPR3a(midipitch)
            gpr3d_Frankland = getFranklandGPR3d(ioi)
            gpr_Frankland_sum = [sum(filter(None, x)) for x in zip(gpr2a_Frankland, gpr2b_Frankland, gpr3a_Frankland, gpr3d_Frankland)]
            lbdm_rpitch = getDegreeChangeLBDMpitch(chromaticinterval)
            lbdm_spitch = getBoundaryStrengthPitch(lbdm_rpitch, chromaticinterval)
            lbdm_rioi = getDegreeChangeLBDMioi(ioi)
            lbdm_sioi = getBoundaryStrengthIOI(lbdm_rioi, ioi)
            lbdm_rrest = getDegreeChangeLBDMrest(restduration_frac)
            lbdm_srest = getBoundaryStrengthRest(lbdm_rrest, restduration_frac)
            lbdm_boundarystrength = getLocalBoundaryStrength(lbdm_spitch, lbdm_sioi, lbdm_srest)
            sorting_year = ''
            #MTC:
            if song_metadata.loc[nlbid,'source_id']:
                sorting_year = source_metadata.loc[song_metadata.loc[nlbid,'source_id'],'sorting_year']
            #RISM
            if 'sorting_year' in song_metadata:
                sorting_year = song_metadata.loc[nlbid,'sorting_year']
            if pd.isna(sorting_year):
                sorting_year = "-1"
            if sorting_year == '':
                sorting_year = "-1" #UGLY
            sorting_year = int(sorting_year)
            if 'ann_bgcorpus' in song_metadata.columns:
                ann_bgcorpus = bool(song_metadata.loc[nlbid,'ann_bgcorpus'])
            else:
                ann_bgcorpus = None
            if 'origin' in song_metadata.columns:
                origin = song_metadata.loc[nlbid,'origin']
            else:
                origin = ''
            try:
                #pass
                timesignature = m21TOTimeSignature(s)
                beat_str, beat_fraction_str = m21TOBeat_str(s)
                beat_float = m21TOBeat_float(s)
                mc = m21TOmetriccontour(s)
                beatstrength = m21TObeatstrength(s)
                beatinsong, beatinphrase, beatfraction = m21TOBeatInSongANDPhrase(s, phrasepos)
                beatinphrase_end = getBeatinphrase_end(beatinphrase, phrase_ix, beat_float)
            except NoMeterError:
                print(nlbid, "has no time signature")
                timesignature = [None]*len(sd)
                beat_str, beat_fraction_str = [None]*len(sd) , [None]*len(sd)
                beat_float = [None]*len(sd)
                mc = [None]*len(sd)
                beatstrength = [None]*len(sd)
                beatinsong, beatinphrase, beatfraction = [None]*len(sd), [None]*len(sd), [None]*len(sd)
                beatinphrase_end = [None]*len(sd)        
        except Exception as e:
            print(f"Features extraction from {nlbid} failed.")
            print(e)
            continue

        seq = {
            'id':nlbid, 'tunefamily': str(song_metadata.loc[nlbid, fieldmap['tunefamily']]),
            'year' : sorting_year,
            'tunefamily_full': str(song_metadata.loc[nlbid, fieldmap['tunefamily_full']]),
            'type' : str(song_metadata.loc[nlbid, 'type']),
            'freemeter' : not hasmeter(s),
            'origin' : origin,
            'features': {
                'pitch': pitch,
                'octave': octave,
                'midipitch': midipitch,
                'contour3' : contour3,
                'contour5' : contour5,
                'pitch40_hewlett': pitch40_hewlett,
                'pitch40_sapp': pitch40_sapp,
                'tonic': tonic,
                'mode': mode,
                'scaledegree': sd,
                'scaledegreespecifier' : sdspec,
                'chromaticscaledegree' : chr_sd,
                'diatonicpitch' : diatonicPitches,
                'diatonicpitch12' : diatonicPitches12,
                'diatonicpitch40' : diatonicPitches40,
                'diatonicinterval': diatonicinterval,
                'chromaticinterval': chromaticinterval,
                'pitchproximity': pitchproximity,
                'pitchreversal': pitchreversal,
                'onsettick': onsettick,
                'duration': duration,
                'duration_frac': duration_frac,
                'duration_fullname': duration_fullname,
                'durationcontour': durationcontour,
                'IOI_frac': ioi_frac,
                'IOI': ioi,
                'IOR_frac': ior_frac,
                'IOR': ior,
                'nextisrest': nextisrest,
                'restduration_frac': restduration_frac,
                'timesignature': timesignature,
                'beat_str': beat_str,
                'beat_fraction_str': beat_fraction_str,
                'beat': beat_float,
                'beatfraction': beatfraction,
                'beatinsong': beatinsong,
                'beatinphrase': beatinphrase,
                'beatinphrase_end': beatinphrase_end,
                'beatstrength': beatstrength,
                'metriccontour':mc,
                'imaweight':ima,
                'imaweight_spectral':ima_spect,
                'imacontour': ic,
                'songpos': songpos,
                'phrasepos': phrasepos,
                'phrase_ix': phrase_ix,
                'phrase_end': phrase_end,
                'gpr2a_Frankland': gpr2a_Frankland,
                'gpr2b_Frankland': gpr2b_Frankland,
                'gpr3a_Frankland': gpr3a_Frankland,
                'gpr3d_Frankland': gpr3d_Frankland,
                'gpr_Frankland_sum': gpr_Frankland_sum,
                'lbdm_spitch': lbdm_spitch,
                'lbdm_sioi': lbdm_sioi,
                'lbdm_srest': lbdm_srest,
                'lbdm_rpitch': lbdm_rpitch,
                'lbdm_rioi': lbdm_rioi,
                'lbdm_rrest': lbdm_rrest,
                'lbdm_boundarystrength': lbdm_boundarystrength
            }
        }
        #if False:
        if textFeatureFile and (nlbid not in nlbids_notvocal):
            try:
                lyrics, noncontentword, wordend, phoneme, rhymes, rhymescontentwords, wordstress, melismastate = \
                    getTextFeatures(nlbid, textFeatureFile)
                seq['features']['lyrics'] = lyrics
                seq['features']['noncontentword'] = noncontentword
                seq['features']['wordend'] = wordend
                seq['features']['phoneme'] = phoneme
                seq['features']['rhymes'] = rhymes
                seq['features']['rhymescontentwords'] = rhymescontentwords
                seq['features']['wordstress'] = wordstress
                seq['features']['melismastate'] = melismastate
            except CacheError:
                pass
                #print(nlbid, 'has no lyrics.')
            except KeyError:
                print(f"{nlbid}: No textfeatures present")
        
        if ann_bgcorpus is not None:
            seq['ann_bgcorpus'] = ann_bgcorpus
        #check lengths
        reflength = len(seq['features']['scaledegree'])
        for feat in seq['features'].keys():
            if len(seq['features'][feat]) != reflength:
                print(f'Error: {nlbid}: length of {feat} differs.')
                print(f'Difference: {len(seq["features"][feat])-reflength}')
                raise FeatLenghtError(nlbid)
        yield seq


def getANNBackgroundCorpusIndices(fsinst_song_metadata):
    ann_song_metadata = pd.read_csv(
        str(Path(mtcannroot,'metadata/MTC-ANN-songs.csv')),
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8',
        names=[
            "songid",
            "NLB_record_number",
            "source_id",
            "serial_number",
            "page",
            "singer_id_s",
            "date_of_recording",
            "place_of_recording",
            "latitude",
            "longitude",
            "title",
            "firstline",
            "strophe_number"
        ]
    )
    #retrieve tf ids of mtc-ann tune families in mtc-fs-inst
    tfids = set(fsinst_song_metadata.loc[ann_song_metadata.index,'tunefamily_id'])
    tfids.remove('')
    tfids = {tf.split('_')[0] for tf in tfids}
    alltfids = set(fsinst_song_metadata['tunefamily_id'])
    alltfids.remove('')
    sel_tfids = {tfid for tfid in alltfids if tfid.split('_')[0] in tfids}
    # now sel_tfids contains all tunefamily_ids of tune families related to the tune families in mtc-ann
    #select songs not in tfs related to mtc-ann
    bg_corpus_mask = ~fsinst_song_metadata['tunefamily_id'].isin(list(sel_tfids))
    bg_corpus = fsinst_song_metadata[bg_corpus_mask]
    #remove songs without tune family label
    bg_corpus = bg_corpus.loc[bg_corpus.tunefamily_id != '']
    # now bg_corpus contains all songs unrelated to mtc-ann's tune families
    return bg_corpus.index

def ann2seqs(startat=None, only=None, missing=False, stopat=None):
    ann_tf_labels = pd.read_csv(
        str(Path(mtcannroot,'metadata/MTC-ANN-tune-family-labels.csv')),
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8',
        names=['ID','TuneFamily']
    )
    ann_song_metadata = pd.read_csv(
        str(Path(mtcannroot,'metadata/MTC-ANN-songs.csv')),
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8',
        names=[
            "songid",
            "NLB_record_number",
            "source_id",
            "serial_number",
            "page",
            "singer_id_s",
            "date_of_recording",
            "place_of_recording",
            "latitude",
            "longitude",
            "title",
            "firstline",
            "strophe_number"
        ]
    )
    #add tune family labels to song_metadata
    ann_full_metadata = pd.concat([ann_tf_labels, ann_song_metadata], axis=1, sort=False)
    #add type ('vocal' for all songs)
    ann_full_metadata['type'] = 'vocal'
    ann_source_metadata = pd.read_csv(
        str(Path(mtcannroot,'metadata/MTC-ANN-sources.csv')),
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8',
        names=[
            "source_id",
            "title",
            "author",
            "place_publisher",
            "dating",
            "sorting_year",
            "type",
            "copy_used",
            "scan_url"]
        )
    print(mtcannkrndir)
    for seq in getSequences(
        krndir=mtcannkrndir,
        song_metadata=ann_full_metadata,
        source_metadata=ann_source_metadata,
        textFeatureFile=str(mtcanntextfeatspath),
        fieldmap = {'tunefamily':'TuneFamily', 'tunefamily_full' : 'TuneFamily'},
        startat=startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

#def lc2seqs():
#    tf_labels = pd.read_csv(mtclcroot+'metadata/MTC-LC-labels.txt', sep='\t', na_filter=False, index_col=0, header=None, encoding='utf8', names=['ID','TuneFamily'])
#    for seq in getSequences(tf_labels.index, krndir=mtclckrndir, jsondir=mtclcjsondir, tf_labels=tf_labels):
#        yield(seq)

#if noann, remove all songs related to MTC-ANN, and remove all songs without tune family label
def fsinst2seqs(startat=None, only=None, missing=False, stopat=None):
    fsinst_song_metadata = pd.read_csv(
        str(Path(mtcfsroot,'metadata/MTC-FS-INST-2.0.csv')),
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8',
        names=[
            "filename",
            "songid",
            "source_id",
            "serial_number",
            "page",
            "singer_id_s",
            "date_of_recording",
            "place_of_recording",
            "latitude",
            "longitude",
            "textfamily_id",
            "title",
            "firstline",
            "tunefamily_id",
            "tunefamily",
            "type",
            "voice_stanza_number",
            "voice_stanza",
            "image_filename_s",
            "audio_filename",
            "variation",
            "confidence",
            "comment",
            "MTC_title",
            "author"
        ]
    )
    fsinst_source_metadata = pd.read_csv(
        str(Path(mtcfsroot,'metadata/MTC-FS-INST-2.0-sources.csv')),
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8',
        names=[
            "source_id",
            "title",
            "author",
            "place_publisher",
            "dating",
            "sorting_year",
            "type",
            "copy_used",
            "scan_url"
        ]
    )
    
    #figure out which songs are not related to MTC-ANN
    #and add to song metadata
    ids_ann_bgcorpus = getANNBackgroundCorpusIndices(fsinst_song_metadata)
    fsinst_song_metadata['ann_bgcorpus'] = False
    fsinst_song_metadata.loc[ids_ann_bgcorpus,'ann_bgcorpus'] = True
    
    for seq in getSequences(
        krndir=mtcfskrndir,
        song_metadata=fsinst_song_metadata,
        source_metadata=fsinst_source_metadata,
        textFeatureFile=str(mtcfsinsttextfeatspath),
        fieldmap = {'tunefamily':'tunefamily_id', 'tunefamily_full' : 'tunefamily'},
        startat=startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def essen2seqs(startat=None, only=None, missing=False, stopat=None):

    essen_song_metadata = pd.read_csv(
        str(essenmetadatapath),
        na_filter=False,
        index_col=0,
        header=0,
        encoding='utf8'
    )
    essen_song_metadata['tunefamily'] = ''
    essen_song_metadata['type'] = 'vocal'
    essen_song_metadata['source_id'] = ''

    for seq in getSequences(
        krndir=essenkrndir,
        song_metadata=essen_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat = startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def chorale2seqs(startat=None, only=None, missing=False, stopat=None):

    chorale_song_metadata = pd.read_csv(
        str(choralemetadatapath),
        na_filter=False,
        index_col=0,
        header=0,
        encoding='utf8'
    )
    chorale_song_metadata['tunefamily'] = ''
    chorale_song_metadata['type'] = 'vocal'
    chorale_song_metadata['source_id'] = ''

    for seq in getSequences(
        krndir=choralekrndir,
        song_metadata=chorale_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat = startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def thesession2seqs(startat=None, only=None, missing=False, stopat=None):

    thesession_song_metadata = pd.read_csv(
        str(thesessionmeatadatapath),
        sep=';',
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8'
    )
    thesession_song_metadata['tunefamily'] = ''
    thesession_song_metadata['type'] = ''
    thesession_song_metadata['source_id'] = ''

    for seq in getSequences(
        krndir=thesessionkrndir,
        song_metadata=thesession_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat = startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def kolberg2seqs(startat=None, only=None, missing=False, stopat=None):

    kolberg_song_metadata = pd.read_csv(
        str(kolbergmeatadatapath),
        sep=';',
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8'
    )
    kolberg_song_metadata['tunefamily'] = ''
    kolberg_song_metadata['type'] = ''
    kolberg_song_metadata['source_id'] = ''

    for seq in getSequences(
        krndir=kolbergkrndir,
        song_metadata=kolberg_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat = startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def cre2seqs(startat=None, only=None, missing=False, stopat=None):

    cre_song_metadata = pd.read_csv(
        str(cremetadatapath),
        sep=';',
        na_filter=False,
        index_col=0,
        header=None,
        encoding='utf8'
    )
    cre_song_metadata['tunefamily'] = ''
    cre_song_metadata['type'] = ''
    cre_song_metadata['source_id'] = ''

    for seq in getSequences(
        krndir=crekrndir,
        song_metadata=cre_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat = startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def rism2seqs(startat=None, only=None, missing=False, stopat=None):

    rism_song_metadata = pd.read_csv(
        rismmetadatapath,
        sep=',',
        na_filter=False,
        index_col=0,
        encoding='utf8'
    )
    rism_song_metadata['tunefamily'] = ''
    rism_song_metadata['type'] = ''
    rism_song_metadata['source_id'] = ''

    rism_song_metadata['sorting_year'] = pd.to_numeric(rism_song_metadata['sorting_year'])
    rism_song_metadata['sorting_year'] = rism_song_metadata['sorting_year'].astype('Int16')

    for seq in getSequences(
        krndir=rismkrndir,
        song_metadata=rism_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat=startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)

def eyck2seqs(startat=None, only=None, missing=False, stopat=None):
    eyck_song_metadata = pd.read_csv(
        str(Path(eyckroot,'metadata.csv')),
        na_filter=False,
        index_col=0,
        header=0,
        encoding='utf8',
        delimiter=';',
        names=[
            "filename",
            "songid",
            "serial_number",
            "serial_number_sub",
            "title",
            "tunefamily_id",
            "tunefamily",
            "variation",
            "source_id",
            "type",
        ]
    )
    eyck_source_metadata = pd.read_csv(
        str(Path(eyckroot,'sources.csv')),
        na_filter=False,
        index_col=0,
        header=0,
        delimiter=';',
        encoding='utf8',
        names=[
            "source_id",
            "title",
            "author",
            "place_publisher",
            "dating",
            "sorting_year",
            "type",
            "copy_used",
            "scan_url"
        ]
    )
    
    for seq in getSequences(
        krndir=eyckkrndir,
        song_metadata=eyck_song_metadata,
        source_metadata=eyck_source_metadata,
        fieldmap = {'tunefamily':'tunefamily_id', 'tunefamily_full' : 'tunefamily'},
        startat=startat,
        only=only,
        missing=missing,
        stopat=stopat,
    ):
        yield(seq)



def main():
    # MTC-LC-1.0 does not have a key tandem in the *kern files. Therefore not possible to compute scale degrees.
    #lc_seqs = lc2seqs()
    #with open('mtclc_sequences.json', 'w') as outfile:
    #    json.dump(lc_seqs, outfile)

    if args.gen_mtcann:
        with open(f'mtcann_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
            for seq in ann2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_mtcfsinst:
        #with open(f'mtcfsinst_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in fsinst2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            with open(os.path.join(outputpath, f'{seq["id"]}.json'), 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')
            
    if args.gen_essen:
        #with open(f'essen_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in essen2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            with open(os.path.join(outputpath, f'{seq["id"]}.json'), 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_chorales:
        with open(f'chorale_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
            for seq in chorale2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_thesession:
        #with open(f'thesession_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in thesession2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            with open(os.path.join(outputpath, f'{seq["id"]}.json'), 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_kolberg:
        #with open(f'kolberg_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in kolberg2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            with open(os.path.join(outputpath, f'{seq["id"]}.json'), 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_cre:
        #with open(f'cre_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in cre2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            with open(os.path.join(outputpath, f'{seq["id"]}.json'), 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_rism:
        rism_song_metadata = pd.read_csv( #needed for file paths
            rismmetadatapath,
            sep=',',
            na_filter=False,
            index_col=0,
            encoding='utf8'
        )
        #with open(f'rism_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in rism2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            outfilename = Path(outputpath, rism_song_metadata.loc[seq['id'],'filename'].replace('.krn','.json')) #.json
            outfilename.parent.mkdir(parents=True, exist_ok=True)
            with open(outfilename, 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_eyck:
        #with open(f'eyck_sequences{"_from"+args.startat if args.startat else ""}.jsonl', 'w') as outfile:
        for seq in eyck2seqs(startat=args.startat, only=args.only, missing=args.missing, stopat=args.stopat):
            with open(os.path.join(outputpath, f'{seq["id"]}.json'), 'w') as outfile:
                outfile.write(json.dumps(seq)+'\n')

if __name__== "__main__":
    main()
