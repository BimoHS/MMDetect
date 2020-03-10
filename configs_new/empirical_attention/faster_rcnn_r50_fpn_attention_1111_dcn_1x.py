_base_ = '../faster_rcnn_r50_fpn_1x.py'
model = dict(
    backbone=dict(
        type='ResNet',
        depth=50,
        num_stages=4,
        out_indices=(0, 1, 2, 3),
        frozen_stages=1,
        style='pytorch',
        gen_attention=dict(
            spatial_range=-1, num_heads=8, attention_type='1111', kv_stride=2),
        stage_with_gen_attention=[[], [], [0, 1, 2, 3, 4, 5], [0, 1, 2]],
        dcn=dict(type='DCN', deformable_groups=1, fallback_on_stride=False),
        stage_with_dcn=(False, True, True, True),
    ))
work_dir = './work_dirs/faster_rcnn_r50_fpn_attention_1111_dcn_1x'
