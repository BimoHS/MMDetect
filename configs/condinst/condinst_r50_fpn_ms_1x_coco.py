_base_ = [
    '../_base_/datasets/coco_instance.py',
    '../_base_/schedules/schedule_1x.py', '../_base_/default_runtime.py'
]

train_pipeline = [
    dict(
        type='LoadImageFromFile',
        file_client_args={{_base_.file_client_args}}),
    dict(type='LoadAnnotations', with_bbox=True, with_mask=True),
    dict(
        type='RandomChoiceResize',
        scales=[(1333, 800), (1333, 768), (1333, 736), (1333, 704),
                (1333, 672), (1333, 640)],
        keep_ratio=True),
    dict(type='RandomFlip', prob=0.5),
    dict(type='PackDetInputs')
]
train_dataloader = dict(dataset=dict(pipeline=train_pipeline))

# model settings
model = dict(
    type='CondInst',
    data_preprocessor=dict(
        type='DetDataPreprocessor',
        mean=[123.675, 116.28, 103.53],
        std=[58.395, 57.12, 57.375],
        bgr_to_rgb=True,
        pad_mask=True,
        pad_size_divisor=32),
    backbone=dict(
        type='ResNet',
        depth=50,
        num_stages=4,
        out_indices=(0, 1, 2, 3),
        frozen_stages=1,
        norm_cfg=dict(type='BN', requires_grad=True),
        norm_eval=True,
        init_cfg=dict(type='Pretrained', checkpoint='torchvision://resnet50'),
        style='pytorch'),
    neck=dict(
        type='FPN',
        in_channels=[256, 512, 1024, 2048],
        out_channels=256,
        start_level=1,
        add_extra_convs='on_output',  # use P5
        num_outs=5,
        relu_before_extra_convs=True),
    bbox_head=dict(
        type='CondInstBboxHead',
        num_params=169,
        num_classes=80,
        in_channels=256,
        stacked_convs=4,
        feat_channels=256,
        strides=[8, 16, 32, 64, 128],
        norm_on_bbox=True,
        centerness_on_reg=True,
        dcn_on_last_conv=False,
        center_sampling=True,
        conv_bias=True,
        loss_cls=dict(
            type='FocalLoss',
            use_sigmoid=True,
            gamma=2.0,
            alpha=0.25,
            loss_weight=1.0),
        loss_bbox=dict(type='GIoULoss', loss_weight=1.0),
        loss_centerness=dict(
            type='CrossEntropyLoss', use_sigmoid=True, loss_weight=1.0)),
    mask_head=dict(
        type='CondInstMaskHead',
        num_layers=3,
        feat_channels=8,
        size_of_interest=8,
        mask_out_stride=4,
        max_masks_to_train=250,
        mask_feature_head=dict(
            in_channels=256,
            feat_channels=128,
            start_level=0,
            end_level=2,
            out_channels=8,
            mask_stride=8,
            num_stacked_convs=4,
            norm_cfg=dict(type='BN', requires_grad=True)),
        loss_mask=dict(
            type='DiceLoss',
            use_sigmoid=True,
            activate=True,
            eps=5e-6,
            loss_weight=1.0)),
    # model training and testing settings
    test_cfg=dict(
        nms_pre=1000,
        min_bbox_size=0,
        score_thr=0.05,
        nms=dict(type='nms', iou_threshold=0.6),
        max_per_img=100,
        mask_thr=0.5))

# optimizer
train_cfg = dict(type='EpochBasedTrainLoop', max_epochs=12, val_interval=1)
optim_wrapper = dict(
    optimizer=dict(lr=0.01),
    paramwise_cfg=dict(bias_lr_mult=2., bias_decay_mult=0.))
optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))

val_evaluator = dict(metric=['bbox', 'segm'])
test_evaluator = val_evaluator
