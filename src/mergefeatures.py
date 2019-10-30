from MTCFeatures.MTCFeatureLoader import MTCFeatureLoader

#fl = MTCFeatureLoader('mtcfsinst_sequences.jsonl.gz')
#seq_iter = fl.merge_sequences('mtcfsinst_textfeatures.jsonl')
#fl.writeJSON('mtcfsinst_sequences_merged.jsonl.gz', seq_iter)

fl = MTCFeatureLoader('essen_sequences.jsonl.gz')
seq_iter = fl.merge_sequences('essen_nextisrest.jsonl')
fl.writeJSON('essen_sequences_merged.jsonl', seq_iter)

