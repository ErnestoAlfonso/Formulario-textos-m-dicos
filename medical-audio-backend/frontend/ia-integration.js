let mediaRecorder = null;
let audioChunks = [];
let iaResultado = null;
let iaStream = null;

document.addEventListener('DOMContentLoaded', () => {
  const btnIA = document.querySelector('[data-action="reconocimiento-asistido"]');
  if (btnIA) {
    btnIA.addEventListener('click', abrirModal);
  }
});

function abrirModal() {
  document.getElementById('modal-ia').style.display = 'flex';
  mostrarEstado('ready');
}

function cerrarModal() {
  document.getElementById('modal-ia').style.display = 'none';
  detenerGrabacion();
}

function mostrarEstado(step) {
  document.getElementById('ia-step-ready').style.display = step === 'ready' ? 'block' : 'none';
  document.getElementById('ia-step-processing').style.display = step === 'processing' ? 'block' : 'none';
  document.getElementById('ia-step-preview').style.display = step === 'preview' ? 'block' : 'none';
}

function actualizarStatus(texto) {
  const el = document.getElementById('ia-status-text');
  if (el) el.textContent = texto;
}

async function iniciarGrabacion() {
  try {
    iaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(iaStream, { mimeType: 'audio/webm' });
    audioChunks = [];

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      await procesarAudio(blob, 'grabacion.webm');
    };

    mediaRecorder.start();
    document.getElementById('btn-grabar').textContent = '⏹ Detener grabación';
    document.getElementById('btn-grabar').onclick = detenerGrabacion;
  } catch (err) {
    alert('No se pudo acceder al micrófono: ' + err.message);
  }
}

function detenerGrabacion() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (iaStream) {
    iaStream.getTracks().forEach(t => t.stop());
    iaStream = null;
  }
  const btn = document.getElementById('btn-grabar');
  if (btn) {
    btn.textContent = '🎙 Grabar ahora';
    btn.onclick = iniciarGrabacion;
  }
}

function volverAGrabar() {
  iaResultado = null;
  mostrarEstado('ready');
}

async function subirAudio(file) {
  if (!file) return;
  await procesarAudio(file, file.name);
}

async function procesarAudio(audioBlob, filename) {
  mostrarEstado('processing');
  actualizarStatus('Transcribiendo audio...');

  const formData = new FormData();
  formData.append('audio', audioBlob, filename);
  formData.append('module', 'both');

  try {
    setTimeout(() => actualizarStatus('Analizando con IA...'), 30000);

    const response = await fetch('http://localhost:8000/process-audio', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err);
    }

    iaResultado = await response.json();
    mostrarPreview(iaResultado);
    mostrarEstado('preview');
  } catch (error) {
    alert('Error al procesar el audio: ' + error.message);
    mostrarEstado('ready');
  }
}

function switchTab(tab) {
  document.querySelectorAll('.ia-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.ia-tab-content').forEach(c => c.style.display = 'none');
  document.querySelector(`.ia-tab[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`ia-tab-${tab}`).style.display = 'block';
}

function mostrarPreview(resultado) {
  // --- Respuestas ---
  const container = document.getElementById('ia-preview-content');
  const answered = (resultado.history?.answers || []).concat(resultado.exam?.answers || []);

  if (answered.length === 0) {
    container.innerHTML = '<p style="color:#888">No se detectaron respuestas en el audio.</p>';
  } else {
    container.innerHTML = answered.map(a => `
      <div class="ia-preview-item">
        <span class="ia-question">${a.question_text}</span>
        <span class="ia-answer">${(a.selected_labels || []).join(', ')}${a.free_text ? ': ' + a.free_text : ''}</span>
      </div>
    `).join('');
  }

  if (resultado.datos_adicionales && resultado.datos_adicionales.length > 0) {
    document.getElementById('ia-datos-adicionales').textContent =
      'Info adicional: ' + resultado.datos_adicionales.join(' | ');
  } else {
    document.getElementById('ia-datos-adicionales').textContent = '';
  }

  // --- Metadata ---
  const meta = resultado.metadata || {};
  document.getElementById('ia-metadata').textContent =
    `⏱ Transcripción: ${meta.transcription_time_seconds || '?'}s · Extracción: ${meta.extraction_time_seconds || '?'}s · Total: ${meta.total_time_seconds || '?'}s · Preguntas respondidas: ${meta.questions_answered || 0}/${meta.questions_total || '?'}`;

  // --- Transcripción ---
  document.getElementById('ia-transcription-text').textContent =
    resultado.transcription || '(sin transcripción)';

  // --- Resumen clínico ---
  document.getElementById('ia-summary-text').textContent =
    resultado.clinical_summary || '(sin resumen)';

  // Mostrar primer tab por defecto
  switchTab('answers');
}

function confirmarResultado() {
  if (iaResultado) {
    rellenarFormulario(iaResultado);
  }
  cerrarModal();
}

function rellenarFormulario(resultado) {
  const allAnswers = [
    ...(resultado.history?.answers || []),
    ...(resultado.exam?.answers || [])
  ];

  allAnswers.forEach(answer => {
    const row = document.querySelector(`[data-question-id="${answer.question_id}"]`);
    if (!row) return;

    answer.selected_codes.forEach(code => {
      const input = row.querySelector(`[data-code="${code}"]`);
      if (input) input.checked = true;
    });

    if (answer.free_text) {
      const textInput = row.querySelector('textarea, input[type="text"]');
      if (textInput) textInput.value = answer.free_text;
    }
  });
}
