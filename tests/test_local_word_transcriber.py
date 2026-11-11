import copy
from pathlib import Path
from uuid import uuid4

import pytest

from lab.tools.local_word_transcriber import LocalWordTranscriber
from threemind_runtime.graph_observation import EDGE_FIELDS, VERSION
from threemind_transformer.local_activity import FIELDS


def heard(channel, strength):
    return {'schema': VERSION, 'node_fields': list(FIELDS), 'edge_fields': list(EDGE_FIELDS),
            'start_us': '500', 'end_us': '20500', 'frames': [
                {'time_us': str(time), 'nodes': [{'id': '1', 'channel': channel,
                    'values': [strength, 0., strength, 0., 0., 0.]}], 'edges': []}
                for time in (500, 20500)]}


def test_raw_word_reader_generalizes_intensity_and_preserves_inputs():
    examples = [{'process': heard(c, s), 'text': word} for c, word in ((17, '甲。'), (91, '乙。')) for s in (.4, .6)]
    before = copy.deepcopy(examples)
    model = LocalWordTranscriber().fit(examples)
    assert model.decode(heard(17, .5))['text'] == '甲。'
    assert model.decode(heard(91, .5))['text'] == '乙。'
    assert examples == before
    with pytest.raises(ValueError, match='labels'):
        model.decode(heard(17, .5) | {'answer': '甲。'})
    with pytest.raises(ValueError, match='sample times'):
        changed = heard(17, .5)
        changed['end_us'] = changed['frames'][-1]['time_us'] = '40500'
        model.decode(changed)


def test_word_reader_checkpoint_preserves_scores_and_does_not_overwrite():
    root = Path(__file__).resolve().parents[1]/'.work'/('test-word-reader-'+uuid4().hex)
    model = LocalWordTranscriber().fit([{'process': heard(17, .4), 'text': '甲。'},
                                       {'process': heard(91, .4), 'text': '乙。'}])
    try:
        model.save(root)
        restored = LocalWordTranscriber.restore(root)
        assert restored.decode(heard(17, .5)) == model.decode(heard(17, .5))
        with pytest.raises(FileExistsError):
            model.save(root)
    finally:
        if root.exists():
            for file in root.iterdir():
                file.unlink()
            root.rmdir()
