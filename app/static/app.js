const state = { mode: 'normal', loopCount: 1, files: [null], jobId: null };
const stages = ['Uploading complete', 'Preparing audio', 'Filtering audio', 'Generating groove', 'Building 3D model', 'Exporting STL', 'Exporting 3MF', 'Ready'];
const slots = document.querySelector('#upload-slots');
const loopWrap = document.querySelector('#loop-count-wrap');
const loopCount = document.querySelector('#loop-count');
const generate = document.querySelector('#generate');
const durationLimit = document.querySelector('#duration-limit');
const statusCard = document.querySelector('#status-card');
const resultCard = document.querySelector('#result-card');

function fileLabel(file) {
  const mb = file.size / 1024 / 1024;
  return `${mb < 1 ? (file.size / 1024).toFixed(0) + ' KB' : mb.toFixed(1) + ' MB'}`;
}

function renderSlots() {
  slots.innerHTML = '';
  const count = state.mode === 'loop' ? state.loopCount : 1;
  state.files.length = count;
  for (let i = 0; i < count; i++) {
    const zone = document.createElement('label');
    zone.className = `drop-zone${state.files[i] ? ' has-file' : ''}`;
    zone.dataset.slot = i;
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.mp3,.wav,audio/mpeg,audio/wav';
    input.setAttribute('aria-label', state.mode === 'loop' ? `Choose audio for loop ${i + 1}` : 'Choose audio file');
    input.addEventListener('change', () => selectFile(i, input.files[0]));
    zone.appendChild(input);
    const file = state.files[i];
    zone.insertAdjacentHTML('beforeend', file
      ? `<span class="upload-icon" aria-hidden="true">✓</span><div><strong>${escapeHtml(file.name)}</strong><p>${state.mode === 'loop' ? `Loop ${i + 1} · first 1.333 seconds used` : 'Ready to process'}</p></div><span class="file-size">${fileLabel(file)}</span>`
      : `<div><span class="upload-icon" aria-hidden="true">＋</span><strong>${state.mode === 'loop' ? `Drop audio for loop ${i + 1}` : 'Drop MP3 or WAV here'}</strong><p>or click to choose a file</p></div>`);
    ['dragenter', 'dragover'].forEach(event => zone.addEventListener(event, e => { e.preventDefault(); zone.classList.add('dragover'); }));
    ['dragleave', 'drop'].forEach(event => zone.addEventListener(event, e => { e.preventDefault(); zone.classList.remove('dragover'); }));
    zone.addEventListener('drop', e => selectFile(i, e.dataTransfer.files[0]));
    slots.appendChild(zone);
  }
  generate.disabled = !state.files.length || state.files.some(file => !file);
}

function selectFile(index, file) {
  if (!file) return;
  const extension = file.name.split('.').pop().toLowerCase();
  if (!['mp3', 'wav'].includes(extension) || file.size > 50 * 1024 * 1024) {
    alert(file.size > 50 * 1024 * 1024 ? 'The uploaded file is too large.' : 'Unsupported audio format. Use MP3 or WAV.');
    return;
  }
  state.files[index] = file;
  renderSlots();
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

document.querySelectorAll('input[name="mode"]').forEach(input => input.addEventListener('change', () => {
  state.mode = input.value;
  loopWrap.hidden = state.mode !== 'loop';
  durationLimit.textContent = state.mode === 'loop' ? 'MAX 1.333 SEC / LOOP' : 'MAX 30 SECONDS';
  state.files = Array(state.mode === 'loop' ? state.loopCount : 1).fill(null);
  renderSlots();
}));
loopCount.addEventListener('change', () => { state.loopCount = Number(loopCount.value); state.files = Array(state.loopCount).fill(null); renderSlots(); });

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = 'Something went wrong.';
    try { message = (await response.json()).detail || message; } catch {}
    throw new Error(message);
  }
  return response.json();
}

generate.addEventListener('click', async () => {
  generate.disabled = true;
  statusCard.hidden = false; resultCard.hidden = true;
  statusCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  try {
    const job = await api('/api/jobs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ mode: state.mode, loop_count: state.loopCount }) });
    state.jobId = job.id;
    updateStatus('Uploading complete');
    for (let i = 0; i < state.files.length; i++) {
      const body = new FormData(); body.append('file', state.files[i]);
      await api(`/api/jobs/${job.id}/audio?slot=${i}`, { method: 'POST', body });
    }
    await api(`/api/jobs/${job.id}/generate`, { method: 'POST' });
    poll(job.id);
  } catch (error) { showError(error.message); }
});

function updateStatus(stage) {
  const index = Math.max(0, stages.indexOf(stage));
  document.querySelector('#status-label').textContent = stage;
  document.querySelector('#stage-count').textContent = `${Math.min(index + 1, 7)} / 7`;
  document.querySelector('#stage-fill').style.width = `${Math.min(100, index / 7 * 100)}%`;
}

async function poll(jobId) {
  try {
    const job = await api(`/api/jobs/${jobId}`);
    updateStatus(job.stage);
    if (job.status === 'ready') return showResult(job);
    if (job.status === 'failed') return showError(job.error || 'Generation failed because the resulting geometry is invalid.');
    setTimeout(() => poll(jobId), 900);
  } catch (error) { showError(error.message); }
}

function showError(message) {
  document.querySelector('#status-label').textContent = 'Generation failed';
  document.querySelector('#status-detail').textContent = message;
  document.querySelector('.pulse').style.background = '#ff7c70';
  generate.disabled = false;
}

function showResult(job) {
  statusCard.hidden = true; resultCard.hidden = false;
  const audio = job.result.audio;
  document.querySelector('#result-eyebrow').textContent = state.mode === 'loop' ? 'INFINITE LOOP RECORD READY' : 'MODEL COMPLETE';
  document.querySelector('#result-title').textContent = state.mode === 'loop' ? `${state.loopCount} locked groove${state.loopCount > 1 ? 's' : ''}, ready.` : 'Your record is ready.';
  const used = state.mode === 'loop' ? '1.333 s each' : `${audio[0].used_duration_sec.toFixed(1)} s`;
  const trimmed = audio.some(item => item.trimmed) ? 'Yes' : 'No';
  document.querySelector('#result-stats').innerHTML = [
    ['Format', '7-inch / 45 RPM'], ['Audio', used], ['Channels', 'Mono'], ['Trimmed', trimmed], ['Nozzle', '0.2 mm'], ['Mesh', `${job.result.debug.triangles.toLocaleString()} triangles`]
  ].map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join('');
  document.querySelector('#debug-output').textContent = JSON.stringify(job.result.debug, null, 2);
  document.querySelector('#preview-player').src = `/api/jobs/${job.id}/preview`;
  document.querySelector('#download-3mf').href = `/api/jobs/${job.id}/record.3mf`;
  document.querySelector('#download-stl').href = `/api/jobs/${job.id}/record.stl`;
  resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.querySelector('#reset').addEventListener('click', () => {
  state.files = Array(state.mode === 'loop' ? state.loopCount : 1).fill(null);
  state.jobId = null; resultCard.hidden = true; statusCard.hidden = true;
  document.querySelector('.pulse').style.background = '';
  document.querySelector('#status-detail').textContent = 'Keep this page open while the groove is calculated.';
  renderSlots(); window.scrollTo({ top: 0, behavior: 'smooth' });
});

renderSlots();

