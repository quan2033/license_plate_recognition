import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://127.0.0.1:8000'
const CAMERA_CAPTURE_INTERVAL_MS = 500

const navItems = [
  { id: 'overview', icon: '▦', label: 'Tổng quan' },
  { id: 'recognition', icon: '◎', label: 'Nhận diện' },
  { id: 'history', icon: '◷', label: 'Lịch sử' },
  { id: 'settings', icon: '⚙', label: 'Cài đặt' },
]

function getHistoryPlates(item) {
  const results = item?.data?.results ?? []
  const videoPlates = item?.data?.plates ?? []
  const plates = [
    ...results.map((plate) => typeof plate === 'string' ? plate : plate?.license_plate),
    ...videoPlates.map((plate) => typeof plate === 'string' ? plate : plate?.license_plate),
  ]

  return [...new Set(plates.filter(Boolean))]
}

function App() {
  const [page, setPage] = useState('recognition')
  const [mode, setMode] = useState('image')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [resultMode, setResultMode] = useState('image')
  const [history, setHistory] = useState([])
  const [apiStatus, setApiStatus] = useState('unknown')
  const [checkingApi, setCheckingApi] = useState(false)
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [cameraBusy, setCameraBusy] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [cameraDevices, setCameraDevices] = useState([])
  const [cameraDeviceId, setCameraDeviceId] = useState('')
  const [cameraImage, setCameraImage] = useState('')
  const [cameraResults, setCameraResults] = useState([])
  const [cameraStreamVersion, setCameraStreamVersion] = useState(0)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const captureCanvasRef = useRef(null)
  const cameraBusyRef = useRef(false)
  const captureRef = useRef(null)
  const lastSavedPlateRef = useRef({})

  const imagePlates = resultMode === 'image'
    ? result?.results ?? []
    : []

  const recognizedPlates = resultMode === 'image'
    ? imagePlates
        .map((plate) => plate.license_plate)
        .filter(Boolean)
    : result?.plates ?? []

  const successfulCount = history.filter(
    (item) => item.plateCount > 0,
  ).length

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  useEffect(() => {
    if (!cameraOn) return undefined

    const timer = window.setInterval(() => {
      captureRef.current?.()
    }, CAMERA_CAPTURE_INTERVAL_MS)

    return () => window.clearInterval(timer)
  }, [cameraOn])

  




async function startCamera(deviceId = cameraDeviceId) {
  setCameraError('');

  try {
    // Dừng camera cũ nếu đang chạy
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    const constraints = {
      audio: false,
      video: {
        ...(deviceId
          ? { deviceId: { exact: deviceId } }
          : { facingMode: 'environment' }),
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    };

    // Mở camera
    const stream = await navigator.mediaDevices.getUserMedia(
      constraints
    );

    streamRef.current = stream;

    // Lấy danh sách camera
    const devices = await navigator.mediaDevices.enumerateDevices();
    const cameras = devices.filter(
      (device) => device.kind === 'videoinput'
    );

    setCameraDevices(cameras);

    // Lấy ID của camera đang sử dụng
    const activeId =
      stream.getVideoTracks()[0]?.getSettings()?.deviceId || '';

    setCameraDeviceId(activeId);

    // Bật trạng thái camera để React hiển thị thẻ video
    setCameraOn(true);
    setCameraStreamVersion((version) => version + 1);
  } catch (err) {
    console.error('Camera error:', err);

    // Dừng luồng camera nếu có lỗi
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    setCameraOn(false);

    setCameraError(
      err.name === 'NotAllowedError'
        ? 'Anh cần cấp quyền truy cập camera cho trình duyệt.'
        : err.name === 'NotFoundError'
          ? 'Không tìm thấy camera trên thiết bị.'
          : err.name === 'NotReadableError'
            ? 'Camera đang được ứng dụng khác sử dụng.'
            : err.message || 'Không thể mở camera.'
    );
  }
}
useEffect(() => {
  if (page !== 'recognition' || !cameraOn || !videoRef.current || !streamRef.current) {
    return;
  }

  const video = videoRef.current;

  video.srcObject = streamRef.current;
  video.muted = true;
  video.playsInline = true;

  video.play().catch((err) => {
    console.error('Không phát được video:', err);
    setCameraError('Không thể hiển thị hình ảnh camera.');
  });
}, [cameraOn, cameraStreamVersion, page]);




  function stopCamera() {
    setCameraOn(false)
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    cameraBusyRef.current = false
    setCameraBusy(false)
  }

  async function captureAndRecognize() {
    const video = videoRef.current
    const canvas = captureCanvasRef.current
    if (!cameraOn || !video || !canvas || video.readyState < 2 || cameraBusyRef.current) return

    cameraBusyRef.current = true
    setCameraBusy(true)
    try {
      const maxWidth = 960
      const scale = Math.min(1, maxWidth / video.videoWidth)
      canvas.width = Math.round(video.videoWidth * scale)
      canvas.height = Math.round(video.videoHeight * scale)
      const context = canvas.getContext('2d')
      context.drawImage(video, 0, 0, canvas.width, canvas.height)

      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82))
      if (!blob) return

      const formData = new FormData()
      formData.append('file', blob, 'camera-frame.jpg')
      const response = await fetch(`${API_URL}/api/recognize/image`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Không nhận diện được khung hình.')
      }

      if (data.image_base64) setCameraImage(`data:image/jpeg;base64,${data.image_base64}`)
      const plates = (data.results ?? []).filter((plate) => plate.license_plate)
      setCameraResults(plates)

      const now = Date.now()
      const newPlates = plates.filter((plate) => {
        const plateText = plate.license_plate.trim().toUpperCase()
        const lastSeen = lastSavedPlateRef.current[plateText] || 0
        if (now - lastSeen < 10000) return false
        lastSavedPlateRef.current[plateText] = now
        return true
      })

      if (newPlates.length) {
        setHistory((previous) => [
          ...newPlates.map((plate, index) => ({
            id: `camera-${now}-${index}`,
            fileName: 'Camera trực tiếp',
            mode: 'image',
            time: new Date().toLocaleString('vi-VN'),
            plateCount: 1,
            data: { ...data, results: [plate] },
          })),
          ...previous,
        ])
      }
    } catch (err) {
      setCameraError(
        err.message === 'Failed to fetch'
          ? 'Không kết nối được FastAPI. Hãy kiểm tra backend đang chạy.'
          : err.message,
      )
    } finally {
      cameraBusyRef.current = false
      setCameraBusy(false)
    }
  }

  // Nạp lại lịch sử đã lưu trong database khi mở trang (chỉ có thông tin chữ, không có ảnh kết quả)
  useEffect(() => {
    let cancelled = false
    let retryTimer = null
    const maxAttempts = 10
    const retryDelayMs = 1000

    async function loadSavedHistory(attempt = 1) {
      try {
        const [videoRes, cameraRes] = await Promise.all([
          fetch(`${API_URL}/api/plates/video?limit=200`),
          fetch(`${API_URL}/api/plates/camera?limit=200`),
        ])
        if (!videoRes.ok || !cameraRes.ok) {
          throw new Error('History API unavailable')
        }
        const [videoData, cameraData] = await Promise.all([videoRes.json(), cameraRes.json()])

        const toDate = (value) => new Date(value)
        const fromVideo = videoData.items.map((row) => {
          const isCamera = row.filename === 'camera-frame.jpg'
          const mode = row.source_type === 'video' ? 'video' : 'image'
          return {
            id: `db-video-${row.id}`,
            fileName: isCamera ? 'Camera trực tiếp' : row.filename || 'Không rõ tên file',
            mode,
            at: toDate(row.created_at),
            plateCount: 1,
            data: mode === 'video'
              ? { plates: [row.license_plate] }
              : { results: [row] },
          }
        })
        const fromCamera = cameraData.items.map((row) => ({
          id: `db-camera-${row.id}`,
          fileName: 'Camera trực tiếp',
          mode: 'image',
          at: toDate(row.captured_at),
          plateCount: 1,
          data: { results: [row] },
        }))

        const saved = [...fromVideo, ...fromCamera]
          .sort((a, b) => b.at - a.at)
          .map(({ at, ...item }) => ({ ...item, time: at.toLocaleString('vi-VN') }))

        if (!cancelled) {
          // Giữ các phiên vừa nhận diện trong lúc chờ nạp và không thêm lại bản ghi đã có.
          setHistory((previous) => {
            const existingIds = new Set(previous.map((item) => item.id))
            return [...previous, ...saved.filter((item) => !existingIds.has(item.id))]
          })
        }
      } catch {
        // Backend có thể chưa sẵn sàng khi frontend vừa mở; tự thử lại thay vì chờ người dùng F5.
        if (!cancelled && attempt < maxAttempts) {
          retryTimer = window.setTimeout(
            () => loadSavedHistory(attempt + 1),
            retryDelayMs,
          )
        }
      }
    }

    loadSavedHistory()
    return () => {
      cancelled = true
      if (retryTimer) window.clearTimeout(retryTimer)
    }
  }, [])

  // luôn giữ bản mới nhất của hàm chụp để interval ở trên không dùng state cũ
  useEffect(() => {
    captureRef.current = captureAndRecognize
  })

  function changeCamera(deviceId) {
    setCameraDeviceId(deviceId)
    startCamera(deviceId)
  }

  function changePage(nextPage) {
    setPage(nextPage)
    setError('')
  }

  function changeMode(nextMode) {
    setMode(nextMode)
    setFile(null)
    setPreview('')
    setResult(null)
    setError('')
  }

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0]
    if (!selectedFile) return

    const allowedExtensions = mode === 'image'
      ? /\.(jpg|jpeg|png|webp)$/i
      : /\.(mp4|avi|mov|mkv)$/i

    if (!allowedExtensions.test(selectedFile.name)) {
      setError(
        mode === 'image'
          ? 'Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP.'
          : 'Chỉ hỗ trợ video MP4, AVI, MOV hoặc MKV.',
      )
      event.target.value = ''
      return
    }

    const maxSize = mode === 'image'
      ? 10 * 1024 * 1024
      : 100 * 1024 * 1024

    if (selectedFile.size > maxSize) {
      setError(
        mode === 'image'
          ? 'Ảnh vượt quá giới hạn 10 MB.'
          : 'Video vượt quá giới hạn 100 MB.',
      )
      event.target.value = ''
      return
    }

    setFile(selectedFile)
    setPreview(URL.createObjectURL(selectedFile))
    setResult(null)
    setError('')
  }

  async function recognize() {
    if (!file) {
      setError('Vui lòng chọn file trước khi nhận diện.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    const endpoint = mode === 'image'
      ? `${API_URL}/api/recognize/image`
      : `${API_URL}/api/recognize/video`

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Không thể nhận diện file.',
        )
      }

      const plateCount = mode === 'image'
        ? (data.results ?? []).filter(
            (plate) => plate.license_plate,
          ).length
        : (data.plates ?? []).length

      setResult(data)
      setResultMode(mode)

      setHistory((previous) => [
        {
          id: `${Date.now()}-${file.name}`,
          fileName: file.name,
          mode,
          time: new Date().toLocaleString('vi-VN'),
          plateCount,
          data,
        },
        ...previous,
      ])
    } catch (err) {
      setError(
        err.message === 'Failed to fetch'
          ? 'Không kết nối được FastAPI. Hãy kiểm tra backend đang chạy.'
          : err.message,
      )
    } finally {
      setLoading(false)
    }
  }

  async function checkApi() {
    setCheckingApi(true)

    try {
      const response = await fetch(`${API_URL}/api/health`)
      if (!response.ok) throw new Error('API unavailable')
      setApiStatus('online')
    } catch {
      setApiStatus('offline')
    } finally {
      setCheckingApi(false)
    }
  }

  function openHistoryItem(item) {
    setSelectedHistoryItem(item)
  }

  function clearSelection() {
    setFile(null)
    setPreview('')
    setResult(null)
    setError('')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault()
            changePage('overview')
          }}
        >
          <span className="brand-mark">DMX</span>
          <span className="brand-copy">
            <strong>ĐỘ<span>MIXI</span></strong>
            <small>NHẬN DIỆN BIỂN SỐ XE</small>
          </span>
        </a>

        <div className="sidebar-label">WORKSPACE</div>

        <nav className="navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => changePage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {page === item.id && <span className="nav-active-dot" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-status-card">
            <span className="status-pulse" />
            <div>
              <strong>Hệ thống nhận diện</strong>
              <small>YOLO + OCR engine</small>
            </div>
          </div>
          <div className="sidebar-user">
            <div className="user-avatar">PL</div>
            <div className="user-copy">
              <strong>PlateVision</strong>
              <small>Local workspace</small>
            </div>
            <span className="user-menu">•••</span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>PlateVision</span>
            <span className="breadcrumb-separator">/</span>
            <strong>
              {navItems.find((item) => item.id === page)?.label ?? 'Tổng quan'}
            </strong>
          </div>

          <div className="topbar-actions">
            <div className={`api-indicator ${apiStatus}`}>
              <span className="status-dot" />
              <span>
                {apiStatus === 'online'
                  ? 'API đang hoạt động'
                  : apiStatus === 'offline'
                    ? 'API ngoại tuyến'
                    : 'API chưa kiểm tra'}
              </span>
            </div>
            <button
              className="topbar-check"
              onClick={checkApi}
              disabled={checkingApi}
              title="Kiểm tra backend"
            >
              {checkingApi ? '...' : '↻'}
            </button>
          </div>
        </header>

        <div className="content-area">
          {page === 'overview' && (
            <section className="page-section">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">WORKSPACE OVERVIEW / 01</span>
                  <h1>Tổng quan hệ thống</h1>
                  <p>Theo dõi nhanh trạng thái nhận diện và hoạt động trong phiên hiện tại.</p>
                </div>
                <button className="primary-button" onClick={() => changePage('recognition')}>
                  <span>◎</span> Mở nhận diện <span className="button-arrow">→</span>
                </button>
              </div>

              <div className="metrics-grid">
                <MetricCard
                  label="Tổng phiên xử lý"
                  value={history.length}
                  icon="◷"
                  note="Trong phiên hiện tại"
                />
                <MetricCard
                  label="Phiên có biển số"
                  value={successfulCount}
                  icon="◎"
                  note="Có ít nhất một biển số"
                />
                <MetricCard
                  label="Camera trực tiếp"
                  value={cameraOn ? 'ON' : 'OFF'}
                  icon="◉"
                  note={cameraOn ? 'Đang phát hiện khung hình' : 'Chưa bật camera'}
                />
                <MetricCard
                  label="Trạng thái API"
                  value={apiStatus === 'online' ? 'ONLINE' : apiStatus === 'offline' ? 'OFFLINE' : '—'}
                  icon="⌘"
                  note="FastAPI backend"
                />
              </div>

              <div className="panel overview-history-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Hoạt động gần đây</h2>
                    <p>Các lượt nhận diện mới nhất trong phiên làm việc</p>
                  </div>
                  <button className="text-button" onClick={() => changePage('history')}>
                    Xem tất cả →
                  </button>
                </div>
                <HistoryTable items={history.slice(0, 5)} onSelect={openHistoryItem} />
              </div>
            </section>
          )}

          {page === 'recognition' && (
            <section className="page-section recognition-page">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">VISION SYSTEM / 02</span>
                  <h1>Nhận diện biển số</h1>
                  <p>Giám sát trực tiếp hoặc tải ảnh, video để phân tích biển số xe.</p>
                </div>
                <div className="live-status">
                  <span className={`status-dot ${cameraOn ? 'online' : ''}`} />
                  {cameraOn ? 'CAMERA ĐANG CHẠY' : 'SẴN SÀNG NHẬN DIỆN'}
                </div>
              </div>

              <div className="recognition-layout">
                <div className="recognition-main-column">
                  <section className="panel live-camera-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="panel-kicker">LIVE INPUT / 01</span>
                        <h2>Camera trực tiếp</h2>
                        <p>Nhận diện tự động từ hình ảnh camera mỗi 500 ms.</p>
                      </div>
                      <span className={`camera-state ${cameraOn ? 'active' : ''}`}>
                        <span className="status-dot" />
                        {cameraOn ? 'LIVE' : 'STANDBY'}
                      </span>
                    </div>

                    <div className={`camera-view ${cameraOn ? 'camera-running' : ''}`}>
                      {cameraOn ? (
                        <video
                          ref={videoRef}
                          className="camera-video"
                          autoPlay
                          muted
                          playsInline
                        />
                      ) : (
                        <div className="camera-placeholder">
                          <div className="camera-placeholder-icon">◉</div>
                          <strong>Camera chưa được bật</strong>
                          <span>Bật camera để tự động quét biển số xe trong khung hình.</span>
                          <button className="primary-button" onClick={() => startCamera()}>
                            <span>▶</span> Bật camera
                          </button>
                        </div>
                      )}

                      {cameraOn && (
                        <div className="camera-overlay">
                          <span className="camera-live-label"><i /> LIVE</span>
                          <span className="camera-scan-label">PLATE DETECTION</span>
                          <span className="scan-corner top-left" />
                          <span className="scan-corner top-right" />
                          <span className="scan-corner bottom-left" />
                          <span className="scan-corner bottom-right" />
                        </div>
                      )}
                    </div>

                    <canvas ref={captureCanvasRef} className="hidden-canvas" />

                    {cameraError && <div className="error-banner">{cameraError}</div>}

                    <div className="camera-controls">
                      <div className="camera-select-wrap">
                        <label htmlFor="camera-select">Thiết bị camera</label>
                        <select
                          id="camera-select"
                          value={cameraDeviceId}
                          onChange={(event) => changeCamera(event.target.value)}
                          disabled={cameraOn && cameraDevices.length === 0}
                        >
                          <option value="">Camera mặc định</option>
                          {cameraDevices.map((device, index) => (
                            <option key={device.deviceId} value={device.deviceId}>
                              {device.label || `Camera ${index + 1}`}
                            </option>
                          ))}
                        </select>
                      </div>

                      {cameraOn ? (
                        <button className="secondary-button stop-camera-button" onClick={stopCamera}>
                          ■ Dừng camera
                        </button>
                      ) : (
                        <button className="secondary-button" onClick={() => startCamera()}>
                          ↻ Kết nối lại
                        </button>
                      )}
                    </div>

                    <div className="camera-footnote">
                      <span className={`status-dot ${cameraBusy ? 'online' : ''}`} />
                      {cameraBusy
                        ? 'Đang gửi khung hình đến hệ thống nhận diện...'
                        : cameraOn
                          ? 'Camera đã kết nối. Hệ thống đang quét tự động.'
                          : 'Cho phép trình duyệt truy cập camera để bắt đầu.'}
                    </div>
                  </section>

                  <section className="panel upload-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="panel-kicker">MANUAL INPUT / 02</span>
                        <h2>Tải ảnh hoặc video</h2>
                        <p>Phân tích file riêng lẻ bằng các API hiện có.</p>
                      </div>
                    </div>

                    <div className="mode-switch">
                      <button
                        className={mode === 'image' ? 'selected' : ''}
                        onClick={() => changeMode('image')}
                      >
                        <span>▧</span> Ảnh
                      </button>
                      <button
                        className={mode === 'video' ? 'selected' : ''}
                        onClick={() => changeMode('video')}
                      >
                        <span>▷</span> Video
                      </button>
                    </div>

                    <div className="upload-workspace">
                      <div className="upload-preview-column">
                        {!file ? (
                          <label className="upload-dropzone">
                            <input
                              type="file"
                              accept={mode === 'image'
                                ? 'image/jpeg,image/png,image/webp'
                                : 'video/mp4,video/avi,video/quicktime,video/x-matroska'}
                              onChange={handleFileChange}
                              hidden
                            />
                            <span className="upload-icon">↑</span>
                            <strong>Kéo file vào đây hoặc chọn file</strong>
                            <span>
                              {mode === 'image'
                                ? 'JPG, PNG, WEBP · Tối đa 10 MB'
                                : 'MP4, AVI, MOV, MKV · Tối đa 100 MB'}
                            </span>
                            <span className="browse-button">Chọn file</span>
                          </label>
                        ) : (
                          <div className="preview-container">
                            <div className="preview-media">
                              {mode === 'image'
                                ? <img src={preview} alt="Ảnh đầu vào" />
                                : <video src={preview} controls />}
                            </div>
                            <div className="selected-file">
                              <span className="file-type-icon">{mode === 'image' ? 'IMG' : 'VID'}</span>
                              <div className="selected-file-info">
                                <strong title={file?.name}>{file?.name}</strong>
                                <span>{file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : ''}</span>
                              </div>
                              <button className="icon-button" onClick={clearSelection} title="Xóa file">×</button>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="secondary-upload-action">
                        {error && <div className="error-banner">{error}</div>}
                        <p>
                          {mode === 'image'
                            ? 'Phân tích một ảnh riêng lẻ bằng API nhận diện ảnh.'
                            : 'Phân tích video bằng API nhận diện video hiện có.'}
                        </p>
                        <button
                          className="primary-button"
                          onClick={recognize}
                          disabled={!file || loading}
                        >
                          {loading
                            ? <><span className="spinner" /> Đang xử lý...</>
                            : <>▶ <span>{mode === 'image' ? 'Nhận diện ảnh' : 'Nhận diện video'}</span> <span className="button-arrow">→</span></>}
                        </button>

                        {result && resultMode === mode && (
                          <div className="upload-result-summary">
                            <strong>Kết quả: {recognizedPlates.length} biển số</strong>
                            {mode === 'video' && (
                              <span>Đã xử lý {result.frames_processed ?? 0} khung hình.</span>
                            )}
                            {mode === 'image' && result.image_base64 && (
                              <img
                                src={`data:image/jpeg;base64,${result.image_base64}`}
                                alt="Ảnh đã xử lý"
                              />
                            )}
                            {mode === 'video' && result.video_url && (
                              <a
                                className="secondary-button video-link"
                                href={`${API_URL}${result.video_url}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Xem video kết quả ↗
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </section>

                  <div className="bottom-status">
                    <span><i className="status-dot online" /> RECOGNITION MODULE</span>
                    <span>LIVE CAMERA / IMAGE / VIDEO</span>
                    <span>POWERED BY YOLO + OCR</span>
                  </div>
                </div>

                <aside className="recognition-side-column">
                  <section className="panel latest-result-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="panel-kicker">LATEST FRAME / 03</span>
                        <h2>Khung hình mới nhất</h2>
                      </div>
                      <span className="result-count">{cameraResults.length} biển số</span>
                    </div>

                    <div className="latest-image">
                      {cameraImage ? (
                        <img src={cameraImage} alt="Khung hình camera mới nhất" />
                      ) : (
                        <div className="latest-image-empty">
                          <span>▧</span>
                          <strong>Chưa có hình ảnh</strong>
                          <small>Bật camera để xem kết quả tại đây.</small>
                        </div>
                      )}
                    </div>

                    <div className="latest-plates">
                      <div className="subsection-title">
                        <strong>Biển số vừa phát hiện</strong>
                        <span>{cameraResults.length}</span>
                      </div>

                      {cameraResults.length ? (
                        cameraResults.map((plate, index) => (
                          <div className="plate-result-row" key={`${plate.license_plate}-${index}`}>
                            <div className="plate-thumbnail">
                              {cameraImage
                                ? <img src={cameraImage} alt="" />
                                : <span>CAR</span>}
                            </div>
                            <div className="plate-result-info">
                              <strong>{plate.license_plate}</strong>
                              <span>
                                Độ tin cậy OCR: {Number(plate.ocr_confidence ?? 0).toFixed(1)}%
                              </span>
                            </div>
                            <span className="plate-confidence">
                              {Number(plate.detection_confidence ?? 0).toFixed(2)}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div className="empty-plates">
                          <span>◎</span>
                          <p>Chưa phát hiện biển số trong khung hình gần nhất.</p>
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="panel recent-history-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="panel-kicker">RECENT RECORDS / 04</span>
                        <h2>Xe đã quét</h2>
                      </div>
                      <button className="text-button" onClick={() => changePage('history')}>
                        Tất cả →
                      </button>
                    </div>

                    <div className="recent-record-list">
                      {history.length ? (
                        history.slice(0, 6).map((item) => {
                          const plate = item.mode === 'image'
                            ? item.data?.results?.[0]?.license_plate
                            : item.data?.plates?.[0]

                          return (
                            <button
                              className="recent-record"
                              key={item.id}
                              onClick={() => openHistoryItem(item)}
                            >
                              <span className="record-icon">
                                {item.fileName === 'Camera trực tiếp' ? 'CAM' : item.mode === 'image' ? 'IMG' : 'VID'}
                              </span>
                              <span className="record-details">
                                <strong>{plate || 'Không đọc được biển số'}</strong>
                                <small>{item.fileName}</small>
                              </span>
                              <span className="record-time">{item.time}</span>
                            </button>
                          )
                        })
                      ) : (
                        <div className="recent-empty">
                          <span>◷</span>
                          <p>Lịch sử xe đã quét sẽ xuất hiện tại đây.</p>
                        </div>
                      )}
                    </div>
                  </section>
                </aside>
              </div>
            </section>
          )}

          {page === 'history' && (
            <section className="page-section">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">ACTIVITY LOG / 03</span>
                  <h1>Lịch sử nhận diện</h1>
                  <p>Xem lại các kết quả được tạo trong phiên trình duyệt hiện tại.</p>
                </div>
                <span className="module-tag">{history.length} PHIÊN</span>
              </div>

              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Nhật ký xử lý</h2>
                    <p>Chọn một dòng để xem lại kết quả nhận diện</p>
                  </div>
                </div>
                <HistoryTable items={history} onSelect={openHistoryItem} />
              </div>

              <div className="overview-note">
                <span className="note-icon">i</span>
                <p>
                  Các biển số đã nhận diện được lưu trong cơ sở dữ liệu SQLite và tự động nạp lại khi mở trang.
                  Ảnh hoặc video nguồn không được lưu cùng bản ghi lịch sử.
                </p>
              </div>
            </section>
          )}

          {page === 'settings' && (
            <section className="page-section">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">SYSTEM CONFIGURATION / 04</span>
                  <h1>Cài đặt hệ thống</h1>
                  <p>Thông tin kết nối và cấu hình giao diện hiện tại.</p>
                </div>
              </div>

              <div className="settings-grid">
                <section className="panel settings-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Kết nối backend</h2>
                      <p>FastAPI recognition service</p>
                    </div>
                    <span className={`connection-tag ${apiStatus}`}>
                      {apiStatus === 'online'
                        ? 'ONLINE'
                        : apiStatus === 'offline'
                          ? 'OFFLINE'
                          : 'UNKNOWN'}
                    </span>
                  </div>

                  <div className="setting-row">
                    <div>
                      <strong>API Base URL</strong>
                      <span>Địa chỉ backend được cấu hình trong frontend</span>
                    </div>
                    <code>{API_URL}</code>
                  </div>
                  <div className="setting-row">
                    <div>
                      <strong>Image recognition</strong>
                      <span>POST /api/recognize/image</span>
                    </div>
                    <span className="enabled-tag">ENABLED</span>
                  </div>
                  <div className="setting-row">
                    <div>
                      <strong>Video recognition</strong>
                      <span>POST /api/recognize/video</span>
                    </div>
                    <span className="enabled-tag">ENABLED</span>
                  </div>

                  <button
                    className="primary-button settings-action"
                    onClick={checkApi}
                    disabled={checkingApi}
                  >
                    {checkingApi ? 'Đang kiểm tra...' : '↻ Kiểm tra kết nối API'}
                  </button>

                  {apiStatus === 'offline' && (
                    <p className="settings-hint">
                      Hãy kiểm tra FastAPI đang chạy và địa chỉ API có chính xác không.
                    </p>
                  )}
                </section>

                <section className="panel settings-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Thông tin ứng dụng</h2>
                      <p>Thành phần đang sử dụng</p>
                    </div>
                  </div>
                  <div className="setting-row">
                    <div><strong>Frontend</strong><span>Giao diện web</span></div>
                    <span className="tech-tag">React + Vite</span>
                  </div>
                  <div className="setting-row">
                    <div><strong>Object detection</strong><span>Phát hiện vùng biển số</span></div>
                    <span className="tech-tag">YOLO</span>
                  </div>
                  <div className="setting-row">
                    <div><strong>Text recognition</strong><span>Đọc ký tự biển số</span></div>
                    <span className="tech-tag">OCR</span>
                  </div>
                  <div className="overview-note inline-note">
                    <span className="note-icon">i</span>
                    <p>Trang này chỉ hiển thị thông tin; không thay đổi cấu hình model hoặc backend.</p>
                  </div>
                </section>
              </div>
            </section>
          )}

          <footer className="page-footer">
            <span>NHẬN DIỆN BIỂN SỐ © 2026</span>
            <span>NHẬN DIỆN BIỂN SỐ XE SYSTEM</span>
            <span>DESIGNED FOR OPERATIONAL CLARITY</span>
          </footer>
        </div>
      </main>

      {selectedHistoryItem && (
        <HistoryDetailModal
          item={selectedHistoryItem}
          onClose={() => setSelectedHistoryItem(null)}
        />
      )}
    </div>
  )
}

function MetricCard({ label, value, icon, note }) {
  return (
    <div className="metric-card">
      <div className="metric-card-top">
        <span>{label}</span>
        <span className="metric-icon">{icon}</span>
      </div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-note">{note}</span>
    </div>
  )
}

function HistoryDetailModal({ item, onClose }) {
  const plates = getHistoryPlates(item)
  const sourceType = item.fileName === 'Camera trực tiếp'
    ? 'Camera trực tiếp'
    : item.mode === 'image'
      ? 'Hình ảnh'
      : 'Video'

  useEffect(() => {
    function closeOnEscape(event) {
      if (event.key === 'Escape') onClose()
    }

    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  return (
    <div className="history-modal-backdrop" onMouseDown={onClose}>
      <section
        className="history-detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="history-detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="history-detail-heading">
          <div>
            <span className="panel-kicker">RECOGNITION DETAIL</span>
            <h2 id="history-detail-title">Chi tiết lịch sử</h2>
          </div>
          <button className="history-modal-close" onClick={onClose} aria-label="Đóng chi tiết">
            ×
          </button>
        </div>

        <div className="history-detail-grid">
          <div className="history-detail-field history-detail-plates">
            <span>Biển số quét được</span>
            {plates.length ? (
              <div className="history-plate-list">
                {plates.map((plate) => <strong key={plate}>{plate}</strong>)}
              </div>
            ) : (
              <strong className="history-no-plate">Không đọc được biển số</strong>
            )}
          </div>
          <div className="history-detail-field">
            <span>Thời gian quét</span>
            <strong>{item.time || 'Không có thông tin'}</strong>
          </div>
          <div className="history-detail-field">
            <span>Nguồn dữ liệu</span>
            <strong>{sourceType}</strong>
          </div>
          <div className="history-detail-field">
            <span>Tên nguồn</span>
            <strong>{item.fileName || 'Không rõ'}</strong>
          </div>
        </div>

        <div className="history-detail-actions">
          <button className="primary-button" onClick={onClose}>Đóng</button>
        </div>
      </section>
    </div>
  )
}

function HistoryTable({ items, onSelect }) {
  if (!items.length) {
    return (
      <div className="table-empty">
        <span>◷</span>
        <strong>Chưa có lịch sử nhận diện</strong>
        <p>Các phiên xử lý thành công sẽ xuất hiện tại đây.</p>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table className="history-table">
        <thead>
          <tr>
            <th>TÊN FILE</th>
            <th>LOẠI DỮ LIỆU</th>
            <th>BIỂN SỐ ĐỌC ĐƯỢC</th>
            <th>THỜI GIAN</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const plates = getHistoryPlates(item)
            return (
            <tr key={item.id}>
              <td>
                <div className="table-file">
                  <span className="table-file-icon">
                    {item.fileName === 'Camera trực tiếp' ? 'CAM' : item.mode === 'image' ? 'IMG' : 'VID'}
                  </span>
                  <strong title={item.fileName}>{item.fileName}</strong>
                </div>
              </td>
              <td>
                <span className="type-pill">
                  {item.fileName === 'Camera trực tiếp' ? 'CAMERA' : item.mode === 'image' ? 'HÌNH ẢNH' : 'VIDEO'}
                </span>
              </td>
              <td>
                <strong className="table-plates">
                  {plates.length ? plates.join(', ') : 'Không đọc được'}
                </strong>
              </td>
              <td className="table-time">{item.time}</td>
              <td>
                <button className="text-button" onClick={() => onSelect(item)}>
                  Xem →
                </button>
              </td>
            </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default App
