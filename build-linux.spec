# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
added_files = [
    ('./gui', 'gui'),
    ('./alembic.ini', '.'),
    ('./src/alembic_src/env.py', 'alembic_src'),
    ('./src/alembic_src/versions/*', 'alembic_src/versions'),
]

a = Analysis(['./src/index.py'],
             pathex=['./dist'],
             binaries=[],
             datas=added_files,
             hiddenimports=['clr'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='hunterlog',
          debug=False,
          bootloader_ignore_signals=False,
          strip=True,
          upx=True,
          upx_exclude=[],
          #icon='./src/assets/logo.ico',
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )


import shutil

shutil.copyfile('logging.conf', '{0}/logging.conf'.format(DISTPATH))