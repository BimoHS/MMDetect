import argparse
import os
import os.path as osp


def parse_args():
    parser = argparse.ArgumentParser(
        description='Convert benchmark model txt to script')
    parser.add_argument(
        'text', type=str, help='Model list files that need to be batch tested')
    parser.add_argument(
        'partition',
        type=str,
        default='openmmlab',
        help='slurm partition name')
    parser.add_argument('checkpoint_dir', help='checkpoint file dir')
    parser.add_argument('--port', type=int, default=29666, help='dist port')
    parser.add_argument(
        '--run', action='store_true', help='run script directly')
    parser.add_argument(
        '--out', type=str, help='path to save model benchmark script')

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    if args.out:
        out_suffix = args.out.split('.')[-1]
        assert args.out.endswith('.sh'), \
            f'Expected out file path suffix is .sh, but get .{out_suffix}'
    assert args.out or args.run, \
        ('Please specify at least one operation (save/run/ the '
         'script) with the argument "--out" or "--run"')

    commands = []
    checkpoint_dir = f'export CHECKPOINT_DIR={args.checkpoint_dir} '
    commands.append(checkpoint_dir)
    commands.append('\n' * 2)

    script_name = osp.join('.dev_scripts', 'slurm_test.sh')
    partition = args.partition  # cluster name
    port = args.port

    with open(args.text, 'r') as f:
        config_info = f.readlines()

        for i, config_str in enumerate(config_info):
            if len(config_str.strip()) == 0:
                continue
            echo_info = f'echo \'{config_str.rstrip()}\' &'
            commands.append(echo_info)
            commands.append('\n')

            config, ckpt, _ = config_str.split(' ')
            fname, _ = osp.splitext(osp.basename(config))
            out_fname = osp.join('tools', 'batch_test', fname)

            command_info = f'GPUS=8  GPUS_PER_NODE=8  ' \
                           f'CPUS_PER_TASK=2 {script_name} '

            command_info += f'{partition} '
            command_info += f'{fname} '
            command_info += f'{config} '
            command_info += f'{ckpt} '
            command_info += f'--work-dir {out_fname} '
            if config.find('rpn_r50_fpn_1x_coco.py') >= 0 or config.find('crpn_r50_caffe_fpn_1x_coco.py') >= 0:
                eval_str = 'proposal_fast'
            else:
                eval_str = 'bbox'
            command_info += f'--eval {eval_str} '
            command_info += f'--cfg-option dist_params.port={port} '
            command_info += ' &'

            commands.append(command_info)

            if i < len(config_info):
                commands.append('\n')
            port += 1

    command_str = ''.join(commands)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(command_str)
    if args.run:
        os.system(command_str)


if __name__ == '__main__':
    main()
