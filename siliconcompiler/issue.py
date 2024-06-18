import git
import json
import os
import shutil
import sys
import tarfile
import time
import tempfile
from datetime import datetime
from siliconcompiler.utils import get_file_template
from siliconcompiler.scheduler import _makecmd, _write_task_manifest, _get_machine_info


def generate_testcase(chip,
                      step,
                      index,
                      archive_name=None,
                      include_pdks=True,
                      include_specific_pdks=None,
                      include_libraries=True,
                      include_specific_libraries=None,
                      hash_files=False):

    # Save original schema since it will be modified
    schema_copy = chip.schema.copy()

    issue_dir = tempfile.TemporaryDirectory(prefix='sc_issue_')

    chip.set('option', 'continue', True)
    if hash_files:
        for key in chip.allkeys():
            if key[0] == 'history':
                continue
            if len(key) > 1:
                if key[-2] == 'option' and key[-1] == 'builddir':
                    continue
                if key[-2] == 'option' and key[-1] == 'cache':
                    continue
            sc_type = chip.get(*key, field='type')
            if 'file' not in sc_type and 'dir' not in sc_type:
                continue
            for _, key_step, key_index in chip.schema._getvals(*key):
                chip.hash_files(*key,
                                check=False,
                                allow_cache=True,
                                step=key_step, index=key_index)

    manifest_path = os.path.join(issue_dir.name, 'orig_manifest.json')
    chip.write_manifest(manifest_path)

    flow = chip.get('option', 'flow')
    tool, task = chip._get_tool_task(step, index, flow=flow)
    task_requires = chip.get('tool', tool, 'task', task, 'require',
                             step=step, index=index)

    # Set copy flags for _collect
    chip.set('option', 'copyall', False)

    def determine_copy(*keypath, in_require):
        copy = in_require

        if keypath[0] == 'library':
            # only copy libraries if selected
            if include_specific_libraries and keypath[1] in include_specific_libraries:
                copy = True
            else:
                copy = include_libraries

            copy = copy and determine_copy(*keypath[2:], in_require=in_require)
        elif keypath[0] == 'pdk':
            # only copy pdks if selected
            if include_specific_pdks and keypath[1] in include_specific_pdks:
                copy = True
            else:
                copy = include_pdks
        elif keypath[0] == 'history':
            # Skip history
            copy = False
        elif keypath[0] == 'package':
            # Skip packages
            copy = False
        elif keypath[0] == 'tool':
            # Only grab tool / tasks
            copy = False
            if list(keypath[0:4]) == ['tool', tool, 'task', task]:
                # Get files associated with testcase tool / task
                copy = True
                if len(keypath) >= 5:
                    if keypath[4] in ('output', 'input', 'report'):
                        # Skip input, output, and report files
                        copy = False
        elif keypath[0] == 'option':
            if keypath[1] == 'builddir':
                # Avoid build directory
                copy = False
            elif keypath[1] == 'cache':
                # Avoid cache directory
                copy = False
            elif keypath[1] == 'cfg':
                # Avoid all of cfg, since we are getting the manifest separately
                copy = False
            elif keypath[1] == 'credentials':
                # Exclude credentials file
                copy = False

        return copy

    for keypath in chip.allkeys():
        if 'default' in keypath:
            continue

        sctype = chip.get(*keypath, field='type')
        if 'file' not in sctype and 'dir' not in sctype:
            continue

        chip.set(*keypath,
                 determine_copy(*keypath,
                                in_require=','.join(keypath) in task_requires),
                 field='copy')

    # Collect files
    work_dir = chip._getworkdir(step=step, index=index)

    # Temporarily change current directory to appear to be issue_dir
    original_cwd = chip.cwd
    chip.cwd = issue_dir.name

    # Get new directories
    job_dir = chip._getworkdir()
    new_work_dir = chip._getworkdir(step=step, index=index)
    collection_dir = chip._getcollectdir()

    # Restore current directory
    chip.cwd = original_cwd

    # Copy in issue run files
    shutil.copytree(work_dir, new_work_dir, dirs_exist_ok=True)
    # Copy in source files
    chip._collect(directory=collection_dir)

    # Set relative path to generate runnable files
    chip._relative_path = new_work_dir
    chip.cwd = issue_dir.name

    # Rewrite replay.sh
    from siliconcompiler import SiliconCompilerError
    try:
        # Rerun setup
        chip.set('arg', 'step', step)
        chip.set('arg', 'index', index)
        func = getattr(chip._get_task_module(step, index, flow=flow), 'pre_process', None)
        if func:
            try:
                # Rerun pre_process
                func(chip)
            except Exception:
                pass
    except SiliconCompilerError:
        pass

    _makecmd(chip,
             tool, task, step, index,
             script_name=f'{chip._getworkdir(step=step, index=index)}/replay.sh',
             include_path=False)

    # Rewrite tool manifest
    chip.set('arg', 'step', step)
    chip.set('arg', 'index', index)
    _write_task_manifest(chip, tool, path=new_work_dir)

    # Restore normal path behavior
    chip._relative_path = None

    # Restore current directory
    chip.cwd = original_cwd

    git_data = {}
    try:
        # Check git information
        repo = git.Repo(path=os.path.join(chip.scroot, '..'))
        commit = repo.head.commit
        git_data['commit'] = commit.hexsha
        git_data['date'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                         time.gmtime(commit.committed_date))
        git_data['author'] = f'{commit.author.name} <{commit.author.email}>'
        git_data['msg'] = commit.message
        # Count number of commits ahead of version
        version_tag = repo.tag(f'v{chip.scversion}')
        count = 0
        for c in commit.iter_parents():
            count += 1
            if c == version_tag.commit:
                break
        git_data['count'] = count
    except git.InvalidGitRepositoryError:
        pass
    except Exception as e:
        git_data['failed'] = str(e)
        pass

    tool, task = chip._get_tool_task(step=step, index=index)

    issue_time = time.time()
    issue_information = {}
    issue_information['environment'] = {key: value for key, value in os.environ.items()}
    issue_information['python'] = {"path": sys.path,
                                   "version": sys.version}
    issue_information['date'] = datetime.fromtimestamp(issue_time).strftime('%Y-%m-%d %H:%M:%S')
    issue_information['machine'] = _get_machine_info()
    issue_information['run'] = {'step': step,
                                'index': index,
                                'libraries_included': include_libraries,
                                'pdks_included': include_pdks,
                                'tool': tool,
                                'toolversion': chip.get('record', 'toolversion',
                                                        step=step, index=index),
                                'task': task}
    issue_information['version'] = {'schema': chip.schemaversion,
                                    'sc': chip.scversion,
                                    'git': git_data}

    if not archive_name:
        design = chip.design
        job = chip.get('option', 'jobname')
        file_time = datetime.fromtimestamp(issue_time).strftime('%Y%m%d-%H%M%S')
        archive_name = f'sc_issue_{design}_{job}_{step}{index}_{file_time}.tar.gz'

    # Make support files
    issue_path = os.path.join(issue_dir.name, 'issue.json')
    with open(issue_path, 'w') as fd:
        json.dump(issue_information, fd, indent=4, sort_keys=True)

    readme_path = os.path.join(issue_dir.name, 'README.txt')
    with open(readme_path, 'w') as f:
        f.write(get_file_template('issue/README.txt').render(
            archive_name=archive_name,
            **issue_information))
    run_path = os.path.join(issue_dir.name, 'run.sh')
    with open(run_path, 'w') as f:
        replay_dir = os.path.relpath(chip._getworkdir(step=step, index=index),
                                     chip.cwd)
        issue_title = f'{chip.design} for {step}{index} using {tool}/{task}'
        f.write(get_file_template('issue/run.sh').render(
            title=issue_title,
            exec_dir=replay_dir
        ))
    os.chmod(run_path, 0o755)

    # Build archive
    arch_base_dir = os.path.basename(archive_name).split('.')[0]
    with tarfile.open(archive_name, "w:gz") as tar:
        # Add individual files
        for path in [manifest_path,
                     issue_path,
                     readme_path,
                     run_path]:
            tar.add(os.path.abspath(path),
                    arcname=os.path.join(arch_base_dir,
                                         os.path.basename(path)))

        tar.add(job_dir,
                arcname=os.path.join(arch_base_dir,
                                     os.path.relpath(job_dir,
                                                     issue_dir.name)))

    issue_dir.cleanup()

    chip.logger.info(f'Generated testcase for {step}{index} in: '
                     f'{os.path.abspath(archive_name)}')

    # Restore original schema
    chip.schema = schema_copy
