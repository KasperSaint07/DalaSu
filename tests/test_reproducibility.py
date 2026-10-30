import pandas as pd
import pytest
from ml.evaluation.check_reproducibility import check


def test_reproducibility_detects_changed_predictions_and_dates(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    a.mkdir(); b.mkdir()
    frame = pd.DataFrame({'date':['2023-01-01','2023-01-02','2023-01-03'],
                          'y_obs':[1.,2.,4.], 'y_pred':[1.1,2.2,3.8]})
    for root in (a,b):
        frame.to_csv(root/'predictions_example.csv', index=False)
    assert check(a,b,['example'])['passed']
    frame.y_pred += 0.01
    frame.to_csv(b/'predictions_example.csv', index=False)
    assert not check(a,b,['example'])['passed']
    frame.loc[0,'date'] = '2022-12-31'
    frame.to_csv(b/'predictions_example.csv', index=False)
    with pytest.raises(AssertionError):
        check(a,b,['example'])
