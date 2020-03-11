_base_ = '../mask_rcnn_r50_fpn_1x.py'
model = dict(
    backbone=dict(
        norm_cfg=dict(type='SyncBN', requires_grad=True),
        norm_eval=False,
        stage_with_gcb=(False, True, True, True),
        gcb=dict(ratio=1. / 16., )))
work_dir = './work_dirs/mask_rcnn_r16_gcb_c3-c5_r50_fpn_syncbn_1x'
