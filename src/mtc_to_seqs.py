import music21 as m21
m21.humdrum.spineParser.flavors['JRP'] = True

import pandas as pd
import numpy as np
import json
import argparse
from fractions import Fraction
import sys
from collections import defaultdict
from pathlib import Path

from MTCFeatures.MTCFeatureLoader import MTCFeatureLoader

epsilon = 0.0001

# These paths must exist:
# ${mtcroot}/MTC-FS-INST-2.0/metadata
# ${mtcroot}/MTC-LC-1.0/metadata
# ${mtcroot}/MTC-ANN-2.0.1/metadata
# ${mtckrnroot}/MTC-FS-INST-2.0/krn
# ${mtckrnroot}/MTC-LC-1.0/krn
# ${mtckrnroot}/MTC-ANN-2.0.1/krn
# ${mtcjsonroot}/MTC-FS-INST-2.0/json
# ${mtcjsonroot}/MTC-LC-1.0/json
# ${mtcjsonroot}/MTC-ANN-2.0.1/json

# The kernfiles should not contain grace notes

parser = argparse.ArgumentParser(description='Convert MTC .krn to feature sequences')
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
    '-essen',
    dest='gen_essen',
    help='Generate sequences for Essen collection.',
    default=False,
    action='store_true'
)
parser.add_argument(
    '-mtcroot',
    type=str,
    help='path to MTC to find metadata',
    default='/Users/pvk/data/MTC/'
)
parser.add_argument(
    '-mtckrnroot',
    type=str,
    help='mtcroot for krn files',
    default='/Users/pvk/data/MTC/'
)
parser.add_argument(
    '-mtcjsonroot',
    type=str,
    help='mtcroot for json files as generated by krn2json',
    default='/Users/pvk/data/MTCjson/'
)
parser.add_argument(
    '-essenkrnroot',
    type=str,
    help='path to essen krn files',
    default='/Users/pvk/data/essen/allkrn'
)
parser.add_argument(
    '-essenjsonroot',
    type=str,
    help='path to essen json files as generated by krn2json',
    default='/Users/pvk/data/essen/alljson'
)
parser.add_argument(
    '-mtcanntextfeatspath',
    type=str,
    help='filename with text features for MTC-ANN',
    default='/Users/pvk/git/MTCExtractFeatures/src/mtcann_textfeatures.jsonl'
)
parser.add_argument(
    '-mtcfsinsttextfeatspath',
    type=str,
    help='filename with text features for MTC-FS-INST',
    default='/Users/pvk/git/MTCExtractFeatures/src/mtcfsinst_textfeatures.jsonl'
)

args = parser.parse_args()

mtcfsroot = Path(args.mtcroot, 'MTC-FS-INST-2.0')
mtcannroot = Path(args.mtcroot, 'MTC-ANN-2.0.1')
mtclcroot = Path(args.mtcroot, 'MTC-LC-1.0')

mtcfskrndir = Path(args.mtckrnroot, 'MTC-FS-INST-2.0','krn')
mtcannkrndir = Path(args.mtckrnroot, 'MTC-ANN-2.0.1','krn')
mtclckrndir = Path(args.mtckrnroot, 'MTC-LC-1.0','krn')

mtcfsjsondir = Path(args.mtcjsonroot, 'MTC-FS-INST-2.0','json')
mtcannjsondir = Path(args.mtcjsonroot, 'MTC-ANN-2.0.1','json')
mtclcjsondir = Path(args.mtcjsonroot, 'MTC-LC-1.0','json')

essenkrndir = Path(args.essenkrnroot)
essenjsondir = Path(args.essenjsonroot)

mtcfsinsttextfeatspath = Path(args.mtcfsinsttextfeatspath)
mtcanntextfeatspath = Path(args.mtcanntextfeatspath)

#song has no meter
class NoMeterError(Exception):
    def __init__(self, arg):
        self.args = arg
    def __str__(self):
        return repr(self.value)
    
#parsing failed
class ParseError(Exception):
    def __init__(self, arg):
        self.args = arg
    def __str__(self):
        return repr(self.value)

#nlbid not in cache
class CacheError(Exception):
    def __init__(self, arg):
        self.args = arg
    def __str__(self):
        return repr(self.value)

#feature vector not of same length
class FeatLenghtError(Exception):
    def __init__(self, arg):
        self.args = arg
    def __str__(self):
        return repr(self.value)

# add left padding to partial measure after repeat bar
def padSplittedBars(s):
    partIds = [part.id for part in s.parts] 
    for partId in partIds: 
        measures = list(s.parts[partId].getElementsByClass('Measure')) 
        for m in zip(measures,measures[1:]): 
            if m[0].quarterLength + m[0].paddingLeft + m[1].quarterLength == m[0].barDuration.quarterLength: 
                m[1].paddingLeft = m[0].quarterLength 
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

# s : flat music21 stream without ties and without grace notes
def hasmeter(s):
    if not s.flat.getElementsByClass('TimeSignature'): return False
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
    metriccontour.insert(0,'+')
    return metriccontour

# s : flat music21 stream without ties and without grace notes
def m21TOscaledegrees(s):
    tonic = s.flat.getElementsByClass('Key')[0].tonic
    scaledegrees = [pitch2scaledegree(x, tonic) for x in s.notes]
    return scaledegrees

# s : flat music21 stream without ties and without grace notes
# output: M: major, m: minor, P: perfect, A: augmented, d: diminished
def m21TOscaleSpecifiers(s):
    tonic = s.flat.getElementsByClass('Key')[0].tonic
    #put A COPY of the tonic in 0th octave
    lowtonic = m21.note.Note(tonic.name)
    lowtonic.octave = 0
    return [pitch2scaledegreeSpecifer(x, lowtonic) for x in s.notes] 

# s : flat music21 stream without ties and without grace notes
# Tonic in 0-octave has value 0
def m21TOdiatonicPitches(s):
    tonic = s.flat.getElementsByClass('Key')[0].tonic
    scaledegrees = [pitch2diatonicPitch(x, tonic) for x in s.notes]
    return scaledegrees

# s : flat music21 stream without ties and without grace notes
def toDiatonicIntervals(s):
    return [0] + [n[1].pitch.diatonicNoteNum - n[0].pitch.diatonicNoteNum for n in zip(s.notes, s.notes[1:]) ]

# s : flat music21 stream without ties and without grace notes
def toChromaticIntervals(s):
    return [0] + [n[1].pitch.midi - n[0].pitch.midi for n in zip(s.notes, s.notes[1:]) ]

# s : flat music21 stream without ties and without grace notes
def m21TOPitches(s):
    return [n.pitch.nameWithOctave for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TOMidiPitch(s):
    return [n.pitch.midi for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TODurations(s):
    return [n.duration.fullName for n in s.notes]

# s : flat music21 stream without ties and without grace notes
def m21TOTimeSignature(s):
    if not hasmeter(s):
        raise NoMeterError("No Meter")
    return [n.getContextByClass('TimeSignature').ratioString for n in s.notes]

def m21TOKey(s):
    keys =  [(k.tonic.name, k.mode) for k in [n.getContextByClass('Key') for n in s.notes]]
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
    if n_first.isNote:
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
        if n.isNote:
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
        if nextnote.isNote:
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

def getIMA(nlbid, path):
    return getFromJson(nlbid, path, 'ima', float)

def getPhrasePos(nlbid, path):
    return getFromJson(nlbid, path, 'phrasepos', float)

def getSongPos(duration):
    npdurations = np.array(duration)
    onsets = np.cumsum(npdurations) - npdurations
    return list(onsets / onsets[-1])

def getPhraseIx(phrasepos):
    current = 0
    phr_ix = []
    for pp in zip(phrasepos,phrasepos[1:]):
        if pp[1] < pp[0]:
            current += 1
        phr_ix.append(current)
    return [0]+phr_ix

def getPitch40(nlbid, path):
    return getFromJson(nlbid, path, 'pitch40', int)

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

def midipitch2contour3(mp, undef='='):
    return [undef] + [getContour3(p[0], p[1]) for p in zip(mp,mp[1:])]

def midipitch2contour5(mp, thresh=3, undef='='):
    return [undef] + [getContour5(p[0], p[1], thresh) for p in zip(mp,mp[1:])]

def getIOR(nlbid, path):
    return getFromJson( nlbid, path, 'ior', float)

def getDuration(nlbid, path):
    return getFromJson(nlbid, path, 'duration', float)

def getIMAcontour(ima):
    imacontour = [value2contour(ima[0], ima[1]) for ima in zip(ima,ima[1:])]
    imacontour.insert(0,'+')
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

#iterator
def getSequences(
        id_list,
        krndir,
        jsondir,
        song_metadata,
        source_metadata,
        textFeatureFile=None,
        fieldmap={'TuneFamily':'TuneFamily', 'TuneFamily_full' : 'TuneFamily'},
        startat=None
    ):
    seen=False
    for nlbid in id_list:
        if startat:
            if nlbid==startat:
                seen=True
            if not seen:
                continue
        print(nlbid)
        try:
            s = parseMelody(str(Path(krndir,nlbid+'.krn')))
        except ParseError:
            print(nlbid, "does not exist")
            continue
        jsondir = str(jsondir)
        sd = m21TOscaledegrees(s)
        sdspec = m21TOscaleSpecifiers(s)
        diatonicPitches = m21TOdiatonicPitches(s)
        diatonicinterval = toDiatonicIntervals(s)
        chromaticinterval = toChromaticIntervals(s)
        ima = getIMA(nlbid, jsondir)
        ic = getIMAcontour(ima)
        pitch = m21TOPitches(s)
        pitch40 = getPitch40(nlbid, jsondir)
        midipitch = m21TOMidiPitch(s)
        tonic, mode = m21TOKey(s)
        contour3 = midipitch2contour3(midipitch)
        contour5 = midipitch2contour5(midipitch, thresh=3)
        duration = getDuration(nlbid, jsondir)
        phrasepos = getPhrasePos(nlbid, jsondir)
        phrase_ix = getPhraseIx(phrasepos)
        songpos = getSongPos(duration)
        try:
            beatinsong, beatinphrase, beatfraction = m21TOBeatInSongANDPhrase(s, phrasepos)
        except NoMeterError:
            beatinsong, beatinphrase, beatfraction = ['0']*len(sd), ['0']*len(sd), ['0']*len(sd)
        ior = getIOR(nlbid, jsondir)
        if song_metadata.loc[nlbid,'source_id']:
            sorting_year = source_metadata.loc[song_metadata.loc[nlbid,'source_id'],'sorting_year']
        else:
            sorting_year = ''
        if sorting_year == '':
            sorting_year = "-1" #UGLY
        sorting_year = int(sorting_year)
        if 'ann_bgcorpus' in song_metadata.columns:
            ann_bgcorpus = bool(song_metadata.loc[nlbid,'ann_bgcorpus'])
        else:
            ann_bgcorpus = None
        try:
            timesignature = m21TOTimeSignature(s)
        except NoMeterError:
            timesignature = ['0/0']*len(sd)
        try:
            beat_str, beat_fraction_str = m21TOBeat_str(s)
        except NoMeterError:
            beat_str, beat_fraction_str = ["1"]*len(sd) , ["0"]*len(sd)
        try:
            beat_float = m21TOBeat_float(s)
        except NoMeterError:
            beat_float = [0.0]*len(sd)
        try:
            mc = m21TOmetriccontour(s)
        except NoMeterError:
            print(nlbid, "has no time signature")
            mc = ['=']*len(sd)
        try:
            beatstrength = m21TObeatstrength(s)
        except NoMeterError:
            beatstrength = [1.0]*len(sd)
        beatinphrase_end = getBeatinphrase_end(beatinphrase, phrase_ix, beat_float)
        seq = {'id':nlbid, 'tunefamily': str(song_metadata.loc[nlbid, fieldmap['tunefamily']]),
                        'year' : sorting_year,
                        'tunefamily_full': str(song_metadata.loc[nlbid, fieldmap['tunefamily_full']]),
                        'type' : str(song_metadata.loc[nlbid, 'type']),
                        'freemeter' : not hasmeter(s),
                        'features': { 'scaledegree': sd,
                                      'scaledegreespecifier' : sdspec,
                                      'tonic': tonic,
                                      'mode': mode,
                                      'metriccontour':mc,
                                      'imaweight':ima,
                                      'pitch40': pitch40,
                                      'midipitch': midipitch,
                                      'diatonicpitch' : diatonicPitches,
                                      'diatonicinterval': diatonicinterval,
                                      'chromaticinterval': chromaticinterval,
                                      'duration': duration,
                                      'beatfraction': beatfraction,
                                      'phrasepos': phrasepos,
                                      'phrase_ix': phrase_ix,
                                      'songpos': songpos,
                                      'beatinsong': beatinsong,
                                      'beatinphrase': beatinphrase,
                                      'beatinphrase_end': beatinphrase_end,
                                      'IOR': ior,
                                      'imacontour': ic,
                                      'pitch': pitch,
                                      'contour3' : contour3,
                                      'contour5' : contour5,
                                      'beatstrength': beatstrength,
                                      'beat_str': beat_str,
                                      'beat_fraction_str': beat_fraction_str,
                                      'beat': beat_float,
                                      'timesignature': timesignature }}
        if textFeatureFile:
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
                print(nlbid, 'has no lyrics.')
        
        if ann_bgcorpus is not None:
            seq['ann_bgcorpus'] = ann_bgcorpus
        #check lengths
        reflength = len(seq['features']['scaledegree'])
        for feat in seq['features'].keys():
            if len(seq['features'][feat]) != reflength:
                print(f'Error: {nlbid}: length of {feat} differs.')
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

def ann2seqs(startat=None):
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
        ann_song_metadata.index,
        krndir=mtcannkrndir,
        jsondir=mtcannjsondir,
        song_metadata=ann_full_metadata,
        source_metadata=ann_source_metadata,
        textFeatureFile=str(mtcanntextfeatspath),
        fieldmap = {'tunefamily':'TuneFamily', 'tunefamily_full' : 'TuneFamily'},
        startat=startat
    ):
        yield(seq)

#def lc2seqs():
#    tf_labels = pd.read_csv(mtclcroot+'metadata/MTC-LC-labels.txt', sep='\t', na_filter=False, index_col=0, header=None, encoding='utf8', names=['ID','TuneFamily'])
#    for seq in getSequences(tf_labels.index, krndir=mtclckrndir, jsondir=mtclcjsondir, tf_labels=tf_labels):
#        yield(seq)

#if noann, remove all songs related to MTC-ANN, and remove all songs without tune family label
def fsinst2seqs(startat=None):
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
        fsinst_song_metadata.index,
        krndir=mtcfskrndir,
        jsondir=mtcfsjsondir,
        song_metadata=fsinst_song_metadata,
        source_metadata=fsinst_source_metadata,
        textFeatureFile=str(mtcfsinsttextfeatspath),
        fieldmap = {'tunefamily':'tunefamily_id', 'tunefamily_full' : 'tunefamily'},
        startat=startat
    ):
        yield(seq)

def essen2seqs(startat=None):
    essen_ids = [fp.stem for fp in essenkrndir.glob('*.krn')]
    essen_song_metadata = pd.DataFrame(index=essen_ids)
    essen_song_metadata['tunefamily'] = ''
    essen_song_metadata['type'] = 'vocal'
    essen_song_metadata['source_id'] = ''

    for seq in getSequences(
        essen_song_metadata.index,
        krndir=essenkrndir,
        jsondir=essenjsondir,
        song_metadata=essen_song_metadata,
        source_metadata=None,
        fieldmap = {'tunefamily':'tunefamily', 'tunefamily_full' : 'tunefamily'},
        startat = startat
    ):
        yield(seq)


def main():
    # MTC-LC-1.0 does not have a key tandem in the *kern files. Therefore not possible to compute scale degrees.
    #lc_seqs = lc2seqs()
    #with open('mtclc_sequences.json', 'w') as outfile:
    #    json.dump(lc_seqs, outfile)

    if args.gen_mtcann:
        with open('mtcann_sequences.jsonl', 'w') as outfile:
            for seq in ann2seqs():
                outfile.write(json.dumps(seq)+'\n')

    if args.gen_mtcfsinst:
        with open('mtcfsinst_sequences.jsonl', 'w') as outfile:
            for seq in fsinst2seqs():
                outfile.write(json.dumps(seq)+'\n')
            
    if args.gen_essen:
        with open('essen_sequences.jsonl', 'w') as outfile:
            for seq in essen2seqs():
                outfile.write(json.dumps(seq)+'\n')

if __name__== "__main__":
    main()
