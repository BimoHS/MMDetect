import cv2
import numpy as np

from mmdet.core.mask import BitmapMasks, PolygonMasks
from ..builder import PIPELINES

_MAX_LEVEL = 10


def level_to_value(level, max_value, random_negative_prob=0.5):
    return (level / _MAX_LEVEL) * max_value


def random_negative(value, random_negative_prob):
    return -value if np.random.rand() < random_negative_prob else value


def bbox2fields():
    bbox2label = {
        'gt_bboxes': 'gt_labels',
        'gt_bboxes_ignore': 'gt_labels_ignore'
    }
    bbox2mask = {
        'gt_bboxes': 'gt_masks',
        'gt_bboxes_ignore': 'gt_masks_ignore'
    }
    bbox2seg = {
        'gt_bboxes': 'gt_semantic_seg',
    }
    return bbox2label, bbox2mask, bbox2seg


@PIPELINES.register_module()
class Translate(object):
    """Translate images along with x-axis or y-axis.

    Args:
        level (int | float): The level for Translate and should be in
            range (0,_MAX_LEVEL]. This value controls the offset used for
            translate the image/bboxes/masks/seg along with x-axis or y-axis.
        prob (float): The probability for perform translating and should be in
            range 0 to 1.
        fill_val (int | float | tuple): The filled values for image border.
            If float, the same fill_val will be used for all the three channels
            of image. If tuple, the should be 3 elements (e.g. equals the
            number of channels for image).
        seg_ignore_label (int): The ``fill_val`` used for segmentation map.
            Note this value must equals ``ignore_label`` in ``semantic_head``
            of the corresponding config. Default 255.
        axis (str): Translate images along with x-axis or y-axis. The option
            of axis is 'x' or 'y'.
        max_translate_offset (int | float): Pixel's maximum offset value for
            Translate along with x-axis or y-axis.
    """

    def __init__(self,
                 level,
                 prob=0.5,
                 fill_val=128,
                 seg_ignore_label=255,
                 axis='x',
                 max_translate_offset=250.,
                 *args,
                 **kwargs):
        assert isinstance(level, (int, float)), \
            'The level must be type int or float.'
        assert 0 <= level <= _MAX_LEVEL, \
            'The level used for calculating Translate\'s offset should be ' \
            'in range (0,_MAX_LEVEL]'
        assert 0 <= prob <= 1.0, \
            'The probability of translation should be in range 0 to 1.'
        if isinstance(fill_val, (float, int)):
            fill_val = tuple([float(fill_val)])
        elif isinstance(fill_val, tuple):
            assert len(fill_val) == 3, \
                'fill_val as tuple must have 3 elements.'
            fill_val = tuple([float(val) for val in fill_val])
        else:
            raise ValueError(
                'fill_val must be a float scale or a tuple with 3 elements.')
        assert np.all([0 <= val <= 255 for val in fill_val]), \
            'all elements of fill_val should between range [0,255].'
        assert axis in ('x', 'y'), \
            'Translate should be alone with x-axis or y-axis.'
        assert isinstance(max_translate_offset, (int, float)), \
            'The max_translate_offset must be type int or float.'
        # the offset for translation
        self.offset = int(level_to_value(level, max_translate_offset))
        self.level = level
        self.prob = prob
        self.fill_val = fill_val
        self.seg_ignore_label = seg_ignore_label
        self.axis = axis
        self.max_translate_offset = max_translate_offset

    @staticmethod
    def get_translate_matrix(offset, axis='x'):
        """Generates the transformation matrix."""
        if axis == 'x':
            trans_matrix = np.float32([[1, 0, offset], [0, 1, 0]])
        elif axis == 'y':
            trans_matrix = np.float32([[1, 0, 0], [0, 1, offset]])
        return trans_matrix

    @staticmethod
    def warpAffine(data,
                   trans_matrix,
                   out_size,
                   fill_val,
                   flags=cv2.INTER_NEAREST,
                   borderMode=cv2.BORDER_CONSTANT):
        """Affine wrapper which transforms the source data using the given
        trans_matrix.

        Args:
            data (np.ndarray): Source data.
            trans_matrix (np.ndarray): Transformation matrix with shape (2, 3).
            out_size (tuple): Size of the output data with format (w, h).
            fill_val (int | float | tuple): Value used in case of a constant
                border.
            flags: Interpolation methods used in ``cv2.warpAffine``.
            borderMode: pixel extrapolation method used in ``cv2.warpAffine``.

        Returns:
            np.ndarray: transformed data with the same shape as input data.
        """
        return cv2.warpAffine(
            data,
            trans_matrix,
            dsize=out_size,  # dsize takes input size as order (w,h).
            flags=flags,
            borderMode=borderMode,
            borderValue=fill_val)

    def __call__(self, results, min_size=0.0, random_negative_prob=0.5):
        """Call function to translate images, bounding boxes, masks and
        semantic segmentation maps.

        Args:
            results (dict): Result dict from loading pipeline.
            min_size (int | float): Minimum pixel size for the
             translated bboxes.
            random_negative_prob (float): The probability that turns the
             offset negative.

        Returns:
            dict: Translated results.
        """
        if np.random.rand() > self.prob:
            return results

        offset = random_negative(self.offset, random_negative_prob)
        # the transformation matrix of cv2
        trans_matrix = self.get_translate_matrix(offset, self.axis)

        self._translate_img(results, trans_matrix, fill_val=self.fill_val)
        self._translate_bboxes(results, offset)
        # fill_val set to 0 for background of mask.
        self._translate_masks(results, trans_matrix, fill_val=0)
        # fill_val set to ``seg_ignore_label`` for the ignored value
        # of segmentation map.
        self._translate_seg(
            results, trans_matrix, fill_val=self.seg_ignore_label)
        self._filter_invalid(results, min_size=min_size)
        return results

    def _translate_img(self, results, trans_matrix, fill_val):
        """Translate images horizontally or vertically, according to
        ``trans_matrix``."""
        for key in results.get('img_fields', ['img']):
            results[key] = self.warpAffine(results[key], trans_matrix,
                                           results[key].shape[:2][::-1],
                                           fill_val)

    def _translate_bboxes(self, results, offset):
        """Shift bboxes horizontally or vertically, according to ``offset``."""
        h, w, c = results['img_shape']
        for key in results.get('bbox_fields', []):
            min_x, min_y, max_x, max_y = np.split(
                results[key], results[key].shape[-1], axis=-1)
            if self.axis == 'x':
                min_x = np.maximum(0, min_x + offset)
                max_x = np.minimum(w, max_x + offset)
            else:
                min_y = np.maximum(0, min_y + offset)
                max_y = np.minimum(h, max_y + offset)

            # the boxs translated outside of image will be filtered along with
            # the corresponding masks, by invoking ``_filter_invalid``.
            results[key] = np.concatenate([min_x, min_y, max_x, max_y],
                                          axis=-1)

    def _translate_masks(self, results, trans_matrix, fill_val=0):
        """Translate masks horizontally or vertically, according to
        ``trans_matrix``."""
        h, w, c = results['img_shape']
        for key in results.get('mask_fields', []):
            if isinstance(results[key], PolygonMasks):
                # convert BitmapMasks to PolygonMasks is not
                # supported currently
                raise NotImplementedError
            translate_masks = []
            for mask in results[key].to_ndarray():
                translate_mask = self.warpAffine(
                    mask.astype(np.uint8), trans_matrix, mask.shape[:2][::-1],
                    fill_val)
                if isinstance(results[key], BitmapMasks):
                    translate_masks.append(translate_mask[np.newaxis, :, :])
                elif isinstance(results[key], PolygonMasks):
                    pass  # TODO suport for type PolygonMasks

            if isinstance(results[key],
                          BitmapMasks) and len(translate_masks) > 0:
                results[key] = BitmapMasks(
                    np.concatenate(translate_masks), h, w)
            elif isinstance(results[key],
                            PolygonMasks) and len(translate_masks) > 0:
                pass  # TODO suport type  PolygonMasks

    def _translate_seg(self, results, trans_matrix, fill_val=255):
        """Translate segmentation maps horizontally or vertically, according to
        ``trans_matrix``."""
        for key in results.get('seg_fields', []):
            results[key] = self.warpAffine(results[key], trans_matrix,
                                           results[key].shape[:2][::-1],
                                           fill_val)

    def _filter_invalid(self, results, min_size=0):
        """Filter bboxes and masks too small or translated out of image."""
        # The key correspondence from bboxes to labels and masks.
        bbox2label, bbox2mask, _ = bbox2fields()
        for key in results.get('bbox_fields', []):
            bbox_w = results[key][:, 2] - results[key][:, 0]
            bbox_h = results[key][:, 3] - results[key][:, 1]
            valid_inds = (bbox_w > min_size) & (bbox_h > min_size)
            results[key] = results[key][valid_inds]
            # label fields. e.g. gt_labels and gt_labels_ignore
            label_key = bbox2label.get(key)
            if label_key in results:
                results[label_key] = results[label_key][valid_inds]
            # mask fields, e.g. gt_masks and gt_masks_ignore
            mask_key = bbox2mask.get(key)
            if mask_key in results:
                results[mask_key] = results[mask_key][valid_inds]
        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += f'(level={self.level}, '
        repr_str += f'prob={self.prob}, '
        repr_str += f'fill_val={self.fill_val}, '
        repr_str += f'seg_ignore_label={self.seg_ignore_label}, '
        repr_str += f'axis={self.axis}, '
        repr_str += f'max_translate_offset={self.max_translate_offset})'
        return repr_str


@PIPELINES.register_module()
class TranslateOnlyBBox(Translate):
    """Translate bboxes (and its corresponding masks, segmentation) along with
    x-axis or y-axis. Note the coordinates of bboxes after translated will not
    be modified while another contents (e.g. image, masks and segmentation)
    will be augmented.

    Args:
        level (int | float): The level for Translate and should be in
            range (0,_MAX_LEVEL]. This value controls the offset used for
            translate the image/bboxes/masks/seg along with x-axis or y-axis.
        prob (float): The probability for perform translating and should be in
            range 0 to 1.
        fill_val (int | float | tuple): The filled values for image border.
            If float, the same fill_val will be used for all the three channels
            of image. If tuple, the should be 3 elements (e.g. equals the
            number of channels for image).
        seg_ignore_label (int): The ``fill_val`` used for segmentation map.
            Note this value must equals ``ignore_label`` in ``semantic_head``
            of the corresponding config. Default 255.
        axis (str): Translate images along with x-axis or y-axis. The option
            of axis is 'x' or 'y'.
        max_translate_offset (int | float): Pixel's maximum offset value for
            Translate along with x-axis or y-axis.
        bbox_aug_factor (int | float): A scale value that controls the
            aug ``prob`` of bboxes. Defaultly should be a positive value
            which greater than 1.
        force_aug (bool): A flag indicates whether to force to do augmentation
            with all bboxes or not. Also may be useful for the unit test.
    """

    def __init__(self,
                 level,
                 prob=0.5,
                 fill_val=128,
                 seg_ignore_label=255,
                 axis='x',
                 max_translate_offset=250.,
                 bbox_aug_factor=3.,
                 force_aug=False,
                 *args,
                 **kwargs):
        super(TranslateOnlyBBox,
              self).__init__(level, prob, fill_val, seg_ignore_label, axis,
                             max_translate_offset)
        assert isinstance(bbox_aug_factor, (int, float)), \
            'bbox_aug_factor must be type int or float.'
        assert bbox_aug_factor >= 1., \
            'bbox_aug_factor must be \'>=1\'.'
        self.bbox_aug_factor = bbox_aug_factor
        self.prob = self.prob / self.bbox_aug_factor
        self.force_aug = force_aug

    def __call__(self, results, random_negative_prob=0.5):
        """Call function to translate images, masks and segmentation maps based
        on cropped regions from bboxes.

        Args:
            results (dict): Result dict from loading pipeline.
            random_negative_prob (float): The probability that turns the offset
             negative.

        Returns:
            dict: Translated results.
        """
        img = results['img']
        bbox2label, bbox2mask, bbox2seg = bbox2fields()
        for key in results.get('bbox_fields', []):
            label_key, mask_key = bbox2label[key], bbox2mask[key]
            if mask_key in results and isinstance(results[mask_key],
                                                  PolygonMasks):
                # convert BitmapMasks to PolygonMasks is not
                # supported currently
                raise NotImplementedError
            bboxes = results[key]
            inds = range(bboxes.shape[0])
            keep_inds = []
            masks, segs = None, None
            if key in bbox2seg and bbox2seg[key] in results:
                segs = results[bbox2seg[key]]
            if mask_key in results:
                masks = results[mask_key].to_ndarray()
            for idx in inds:
                if np.random.rand() < self.prob or self.force_aug:
                    # trans_matrix
                    offset = random_negative(self.offset, random_negative_prob)
                    trans_matrix = self.get_translate_matrix(offset, self.axis)
                    # translate image
                    min_x, min_y, max_x, max_y = bboxes[idx].copy().astype(
                        np.int32)
                    bbox_content = img[min_y:max_y, min_x:max_x, :]
                    augmented_bbox_content = self.warpAffine(
                        bbox_content, trans_matrix,
                        bbox_content.shape[:-1][::-1], self.fill_val)
                    img[min_y:max_y, min_x:max_x] = augmented_bbox_content

                    # translate segmentations
                    if segs is not None and len(segs) > 0:
                        seg_content = segs[min_y:max_y, min_x:max_x]
                        augmented_seg_content = self.warpAffine(
                            seg_content, trans_matrix, seg_content.shape[::-1],
                            self.seg_ignore_label)
                        results[bbox2seg[key]][
                            min_y:max_y, min_x:max_x] = augmented_seg_content

                    # filter mask and label which have no foregrounds within
                    # the translated region according to bbox
                    if abs(offset) >= min(bbox_content.shape[:2]):
                        continue
                    keep_inds.append(idx)

                    # translate masks
                    if masks is not None and len(masks) > 0:
                        mask_content = masks[idx][min_y:max_y, min_x:max_x]
                        augmented_mask_content = self.warpAffine(
                            mask_content, trans_matrix,
                            mask_content.shape[::-1], 0)
                        masks[idx][min_y:max_y,
                                   min_x:max_x] = augmented_mask_content

            # if masks is not None and len(masks) > 0 and isinstance(
            #         results[mask_key], BitmapMasks):
            #     results[mask_key] = BitmapMasks(masks, img.shape[0],
            #                                     img.shape[1])

            if keep_inds:
                results[key] = results[key][keep_inds]
                if label_key in results:
                    results[label_key] = results[label_key][keep_inds]
                if masks is not None and len(masks) > 0 and isinstance(
                        results[mask_key], BitmapMasks):
                    results[mask_key] = BitmapMasks(masks[keep_inds],
                                                    img.shape[0], img.shape[1])
        return results

    def __repr__(self):
        repr_str = self.__class__.__name__
        repr_str += f'(level={self.level}, '
        repr_str += f'prob={self.prob}, '
        repr_str += f'fill_val={self.fill_val}, '
        repr_str += f'seg_ignore_label={self.seg_ignore_label}, '
        repr_str += f'axis={self.axis}, '
        repr_str += f'max_translate_offset={self.max_translate_offset}, '
        repr_str += f'bbox_aug_factor={self.bbox_aug_factor}, '
        repr_str += f'force_aug={self.force_aug})'
        return repr_str
