_base_ = '../faster_rcnn/faster_rcnn_r50_fpn_1x_coco.py'
model = dict(
    bbox_roi_extractor=dict(
        type='SingleRoIExtractor',
        roi_layer=dict(
            _delete_=True,
            type='ModulatedDeformRoIPoolingPack',
            out_size=7,
            out_channels=256,
            no_trans=False,
            group_size=1,
            trans_std=0.1),
        out_channels=256,
        featmap_strides=[4, 8, 16, 32]))
work_dir = './work_dirs/faster_rcnn_mdpool_r50_fpn_1x'
