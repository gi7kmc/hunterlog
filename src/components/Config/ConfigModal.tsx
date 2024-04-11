import * as React from 'react';
import clsx from 'clsx';
import { styled, css } from '@mui/system';
import { Modal as BaseModal } from '@mui/base/Modal';
import Button from '@mui/material/Button';
import { UserConfig } from '../../@types/Config';
import TextField from '@mui/material/TextField';
import Stack from '@mui/material/Stack';
import { FormControlLabel, Radio, RadioGroup } from '@mui/material';
import Checkbox from '@mui/material/Checkbox';

const def: UserConfig = {
    my_call: 'N0CALL',
    my_grid6: 'FN31pr',
    default_pwr: 0,
    flr_host: '127.0.0.1',
    flr_port: 12345,
    adif_host: '127.0.0.1',
    adif_port: 12345,
    logger_type: 0,
    size_x: 0, // not displayed in frontend
    size_y: 0, // not displayed in frontend
    is_max: false // not displayed in frontend
};

export default function ConfigModal() {
    const [open, setOpen] = React.useState(false);
    const [config, setConfig] = React.useState<UserConfig>(def);
    const [imperialChecked, setImperialChecked] = React.useState(true);

    const handleOpen = () => setOpen(true);
    const handleClose = () => setOpen(false);
    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        let x = (event.target as HTMLInputElement).value;
        let y = parseInt(x);

        let newCfg: UserConfig = { ...config, logger_type: y };
        setConfig(newCfg);
    };

    React.useEffect(() => {
        window.addEventListener('pywebviewready', function () {
            let x = window.pywebview.api.get_user_config();
            x.then((r: string) => {
                if (r == null) return;
                //console.log(`got config ${r}`);
                var cfg = JSON.parse(r) as UserConfig;
                setConfig(cfg);
            });

            let units = window.localStorage.getItem("USE_FREEDOM_UNITS") || '1';
            let use_imperial = parseInt(units);
            setImperialChecked(use_imperial != 0 ? true : false);
        });
    }, []);

    const handleSave = () => {
        if (window.pywebview !== undefined) {
            window.pywebview.api.set_user_config(config);
            handleClose();
        }
    };

    const handleCheckedChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setImperialChecked(event.target.checked);
        let x = event.target.checked ? '1' : '0';
        window.localStorage.setItem("USE_FREEDOM_UNITS", x);
    };

    return (
        <div>
            <Button color='primary' onClick={handleOpen}>
                Configuration
            </Button>
            <Modal
                aria-labelledby="unstyled-modal-title"
                aria-describedby="unstyled-modal-description"
                open={open}
                onClose={handleClose}
                slots={{ backdrop: StyledBackdrop }}
            >
                <ModalContent sx={{ width: 500 }}>
                    <h2 id="unstyled-modal-title" className="modal-title">
                        Configuration
                    </h2>
                    <p id="unstyled-modal-description" className="modal-description">
                        Please update your settings.
                    </p>
                    <Stack direction={'row'} spacing={1}>
                        <TextField id="my_call" label="My Callsign"
                            value={config?.my_call}
                            onChange={(e) => {
                                setConfig({ ...config, my_call: e.target.value });
                            }} />
                        <TextField id="my_grid6" label="My Gridsquare (6 digit)"
                            value={config?.my_grid6}
                            onChange={(e) => {
                                setConfig({ ...config, my_grid6: e.target.value });
                            }} />
                    </Stack>
                    <Stack direction={'row'} spacing={1}>
                        <TextField id="default_pwr" label="Default TX Power"
                            value={config?.default_pwr}
                            onChange={(e) => {
                                setConfig({ ...config, default_pwr: Number.parseInt(e.target.value) });
                            }} />
                        <FormControlLabel control={
                            <Checkbox defaultChecked checked={imperialChecked}
                                onChange={handleCheckedChange} />
                        } label="Display Imperial Units" />
                    </Stack>
                    <Stack direction={'row'} spacing={1}>
                        <TextField id="flr_host" label="FLRIG Host (IP)"
                            value={config?.flr_host}
                            onChange={(e) => {
                                setConfig({ ...config, flr_host: e.target.value });
                            }} />
                        <TextField id="flr_port" label="FLRIG Port (number)"
                            value={config?.flr_port}
                            onChange={(e) => {
                                setConfig({ ...config, flr_port: Number.parseInt(e.target.value) });
                            }} />
                    </Stack>
                    <RadioGroup
                        defaultValue="0"
                        row
                        name="radio-buttons-group"
                        value={config?.logger_type}
                        onChange={handleChange}
                    >
                        <FormControlLabel value="0" control={<Radio />} label="TCP (Logger32)" />
                        <FormControlLabel value="1" control={<Radio />} label="UDP (Log4om)" />
                        <FormControlLabel value="2" control={<Radio />} label="AcLog" />
                    </RadioGroup>
                    <Stack direction={'row'} spacing={1}>
                        <TextField id="adif_host" label="Remote ADIF Host (IP)"
                            value={config?.adif_host}
                            onChange={(e) => {
                                setConfig({ ...config, adif_host: e.target.value });
                            }} />
                        <TextField id="adif_port" label="Remote ADIF Port (number)"
                            value={config?.adif_port}
                            onChange={(e) => {
                                setConfig({ ...config, adif_port: Number.parseInt(e.target.value) });
                            }} />
                    </Stack>

                    <Button onClick={handleSave}>Save</Button>
                    <Button onClick={handleClose}>Cancel</Button>
                </ModalContent>
            </Modal>
        </div >
    );
}

const Backdrop = React.forwardRef<
    HTMLDivElement,
    { open?: boolean; className: string }
>((props, ref) => {
    const { open, className, ...other } = props;
    return (
        <div
            className={clsx({ 'base-Backdrop-open': open }, className)}
            ref={ref}
            {...other}
        />
    );
});

const blue = {
    200: '#99CCFF',
    300: '#66B2FF',
    400: '#3399FF',
    500: '#007FFF',
    600: '#0072E5',
    700: '#0066CC',
};

const grey = {
    50: '#F3F6F9',
    100: '#E5EAF2',
    200: '#DAE2ED',
    300: '#C7D0DD',
    400: '#B0B8C4',
    500: '#9DA8B7',
    600: '#6B7A90',
    700: '#434D5B',
    800: '#303740',
    900: '#1C2025',
};

const Modal = styled(BaseModal)`
  position: fixed;
  z-index: 1300;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const StyledBackdrop = styled(Backdrop)`
  z-index: -1;
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.5);
  -webkit-tap-highlight-color: transparent;
`;

const ModalContent = styled('div')(
    ({ theme }) => css`
    /*font-family: 'IBM Plex Sans', sans-serif;*/
    font-weight: 500;
    text-align: start;
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
    background-color: ${theme.palette.mode === 'dark' ? grey[900] : '#fff'};
    border-radius: 8px;
    border: 1px solid ${theme.palette.mode === 'dark' ? grey[700] : grey[200]};
    box-shadow: 0 4px 12px
      ${theme.palette.mode === 'dark' ? 'rgb(0 0 0 / 0.5)' : 'rgb(0 0 0 / 0.2)'};
    padding: 24px;
    color: ${theme.palette.mode === 'dark' ? grey[50] : grey[900]};

    & .modal-title {
      margin: 0;
      line-height: 1.5rem;
      margin-bottom: 8px;
    }

    & .modal-description {
      margin: 0;
      line-height: 1.5rem;
      font-weight: 400;
      color: ${theme.palette.mode === 'dark' ? grey[400] : grey[800]};
      margin-bottom: 4px;
    }
  `,
);

const TriggerButton = styled('button')(
    ({ theme }) => css`
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    font-size: 0.875rem;
    line-height: 1.5;
    padding: 8px 16px;
    border-radius: 8px;
    transition: all 150ms ease;
    cursor: pointer;
    background: ${theme.palette.mode === 'dark' ? grey[900] : '#fff'};
    border: 1px solid ${theme.palette.mode === 'dark' ? grey[700] : grey[200]};
    color: ${theme.palette.mode === 'dark' ? grey[200] : grey[900]};
    box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);

    &:hover {
      background: ${theme.palette.mode === 'dark' ? grey[800] : grey[50]};
      border-color: ${theme.palette.mode === 'dark' ? grey[600] : grey[300]};
    }

    &:active {
      background: ${theme.palette.mode === 'dark' ? grey[700] : grey[100]};
    }

    &:focus-visible {
      box-shadow: 0 0 0 4px ${theme.palette.mode === 'dark' ? blue[300] : blue[200]};
      outline: none;
    }
  `,
);
