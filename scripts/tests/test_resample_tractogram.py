#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile

from scilpy.io.fetcher import fetch_data, get_home, get_testing_files_dict

# If they already exist, this only takes 5 seconds (check md5sum)
fetch_data(get_testing_files_dict(), keys=['tracking.zip'])
tmp_dir = tempfile.TemporaryDirectory()


def test_help_option(script_runner):
    ret = script_runner.run('scil_resample_tractogram.py', '--help')
    assert ret.success


def test_execution_downsample(script_runner):
    os.chdir(os.path.expanduser(tmp_dir.name))
    in_tracto = os.path.join(get_home(), 'tracking',
                             'union_shuffle_sub.trk')
    ret = script_runner.run('scil_resample_tractogram.py', in_tracto,
                            '500', 'union_shuffle_sub_downsampled.trk')
    assert ret.success


def test_execution_upsample(script_runner):
    os.chdir(os.path.expanduser(tmp_dir.name))
    in_tracto = os.path.join(get_home(), 'tracking',
                             'union_shuffle_sub.trk')
    ret = script_runner.run('scil_resample_tractogram.py', in_tracto,
                            '2000', 'union_shuffle_sub_upsampled.trk',
                            '--point_wise_std', '0.5')
    assert ret.success
