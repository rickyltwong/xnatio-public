# DICOM C-STORE Upload

`xnatio upload-dicom` supports sending DICOM files directly to an XNAT SCP
using the DICOM C-STORE protocol. This is useful when REST import is not
available or when you need SCP-level behavior.

## Configuration

Set these optional variables in `.env` (or pass flags):

```
XNAT_DICOM_HOST=your-xnat.example.org
XNAT_DICOM_PORT=8104
XNAT_DICOM_CALLED_AET=XNAT
XNAT_DICOM_CALLING_AET=XNATIO
```

## Usage

```bash
xio upload-dicom PROJECT SUBJECT SESSION /path/to/dicom_dir \
  --transport dicom-store \
  --dicom-host 192.168.1.10 \
  --dicom-port 8104 \
  --dicom-called-aet XNAT \
  --dicom-calling-aet XNATIO \
  --dicom-batches 45 -v
```

## Notes

- Input must be a directory; archives are not supported for C-STORE.
- Each batch uses its own association; tune `--dicom-batches` for throughput.
- Logs are written to a temporary workspace and reported after completion.
