function updateRowAvailability(row) {
  const select = row.querySelector('.status-select');
  const startInput = row.querySelector('.start-input');
  const endInput = row.querySelector('.end-input');
  const enabled = select && select.value === 'available';

  if (startInput) {
    startInput.disabled = !enabled;
    if (!enabled) {
      startInput.value = '';
    } else if (!startInput.value) {
      startInput.value = '09:00';
    }
  }

  if (endInput) {
    endInput.disabled = !enabled;
    if (!enabled) {
      endInput.value = '';
    } else if (!endInput.value) {
      endInput.value = '18:00';
    }
  }
}

function initShiftForm() {
  const rows = document.querySelectorAll('.day-row');
  if (!rows.length) return;

  rows.forEach((row) => {
    const select = row.querySelector('.status-select');
    if (select) {
      select.addEventListener('change', () => updateRowAvailability(row));
    }
    updateRowAvailability(row);
  });

  const fillAllAvailable = document.querySelector('[data-fill="all-available"]');
  if (fillAllAvailable) {
    fillAllAvailable.addEventListener('click', () => {
      rows.forEach((row) => {
        const select = row.querySelector('.status-select');
        const startInput = row.querySelector('.start-input');
        const endInput = row.querySelector('.end-input');
        if (select) select.value = 'available';
        if (startInput) startInput.value = '09:00';
        if (endInput) endInput.value = '18:00';
        updateRowAvailability(row);
      });
    });
  }

  const fillAllRequested = document.querySelector('[data-fill="all-requested"]');
  if (fillAllRequested) {
    fillAllRequested.addEventListener('click', () => {
      rows.forEach((row) => {
        const select = row.querySelector('.status-select');
        if (select) select.value = 'requested_off';
        updateRowAvailability(row);
      });
    });
  }
}

document.addEventListener('DOMContentLoaded', initShiftForm);
