from MTCFeatures.MTCFeatureLoader import MTCFeatureLoader

#fl = MTCFeatureLoader('mtcfsinst_sequences.jsonl.gz')
#seq_iter = fl.merge_sequences('mtcfsinst_textfeatures_nopunctuation.jsonl')
#fl.writeJSON('mtcfsinst_sequences_merged.jsonl.gz', seq_iter)

fl = MTCFeatureLoader('mtcann_sequences.jsonl.gz')
seq_iter = fl.merge_sequences('mtcann_textfeatures_nopunctuation.jsonl')
fl.writeJSON('mtcann_sequences_merged.jsonl.gz', seq_iter)

