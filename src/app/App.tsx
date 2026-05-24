import { useState, useEffect, useRef } from 'react';

const AI_SERVER = 'http://localhost:8000';

export default function App() {
  const [heaterOn, setHeaterOn] = useState(false);
  const [acOn, setAcOn] = useState(false);
  const [doorOpen, setDoorOpen] = useState(false);
  const [windowsOpen, setWindowsOpen] = useState(false);

  const [temperature, setTemperature] = useState(22);
  const [humidity, setHumidity] = useState(45);
  const [co2, setCo2] = useState(400);

  // AI mode state
  const [aiMode, setAiMode] = useState(false);
  const [aiStatus, setAiStatus] = useState<'idle' | 'thinking' | 'error'>('idle');
  const [aiConfidence, setAiConfidence] = useState<Record<string, number> | null>(null);
  const [aiLastAction, setAiLastAction] = useState<string>('');

  // Refs so the AI polling closure always sees latest sensor values
  const tempRef = useRef(temperature);
  const humRef  = useRef(humidity);
  const co2Ref  = useRef(co2);
  useEffect(() => { tempRef.current = temperature; }, [temperature]);
  useEffect(() => { humRef.current  = humidity;    }, [humidity]);
  useEffect(() => { co2Ref.current  = co2;         }, [co2]);

  useEffect(() => {
    const interval = setInterval(() => {
      setTemperature(prev => {
        let newTemp = prev;
        if (heaterOn) newTemp += 0.5;
        if (acOn) newTemp -= 0.5;
        if (windowsOpen || doorOpen) newTemp += (20 - prev) * 0.05;
        return Math.max(15, Math.min(35, Number(newTemp.toFixed(1))));
      });

      setHumidity(prev => {
        let newHumidity = prev;
        if (heaterOn) newHumidity -= 0.3;
        if (acOn) newHumidity -= 0.2;
        if (windowsOpen || doorOpen) newHumidity += 0.4;
        return Math.max(20, Math.min(80, Number(newHumidity.toFixed(1))));
      });

      setCo2(prev => {
        let newCo2 = prev;
        if (windowsOpen || doorOpen) newCo2 -= 5;
        else newCo2 += 2;
        return Math.max(350, Math.min(1500, Math.round(newCo2)));
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [heaterOn, acOn, windowsOpen, doorOpen]);

  // ── AI polling loop ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!aiMode) {
      setAiStatus('idle');
      return;
    }

    const poll = async () => {
      setAiStatus('thinking');
      try {
        const res = await fetch(`${AI_SERVER}/predict`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            temperature: tempRef.current,
            humidity:    humRef.current,
            co2:         co2Ref.current,
          }),
        });
        const data = await res.json();

        setHeaterOn(data.heater);
        setAcOn(data.ac);
        setWindowsOpen(data.window);
        setAiConfidence(data.confidence);
        setAiStatus('idle');

        const actions = [
          data.heater  ? 'HEATER ON'  : 'HEATER OFF',
          data.ac      ? 'AC ON'      : 'AC OFF',
          data.window  ? 'WIN OPEN'   : 'WIN CLOSED',
        ].join(' · ');
        setAiLastAction(actions);
      } catch {
        setAiStatus('error');
      }
    };

    poll(); // immediate first call
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [aiMode]);

  return (
    <div className="size-full flex flex-col items-center justify-center bg-[#1a1a2e] p-8">
      {/* AI Mode Toggle */}
      <div className="flex items-center gap-4 mb-6 bg-[#0f0f1e] border-2 border-[#00ff00] px-6 py-3 font-mono">
        <span className="text-[#00ff00] text-sm">AI CONTROL</span>
        <button
          onClick={() => setAiMode(m => !m)}
          className={`w-14 h-7 rounded-full border-2 relative transition-colors duration-300 ${
            aiMode ? 'bg-[#00ff00] border-[#00ff00]' : 'bg-transparent border-[#006600]'
          }`}
        >
          <span className={`absolute top-0.5 w-5 h-5 rounded-full transition-all duration-300 ${
            aiMode ? 'left-7 bg-[#0f0f1e]' : 'left-0.5 bg-[#006600]'
          }`} />
        </button>
        <span className={`text-xs ${
          aiStatus === 'error'    ? 'text-red-400' :
          aiStatus === 'thinking' ? 'text-yellow-400 animate-pulse' :
          aiMode                  ? 'text-[#00ff00]' : 'text-[#006600]'
        }`}>
          {aiStatus === 'error'    ? '⚠ SERVER OFFLINE' :
           aiStatus === 'thinking' ? '◌ THINKING…' :
           aiMode                  ? '● ACTIVE' : '○ MANUAL'}
        </span>
        {aiMode && aiLastAction && (
          <span className="text-[#00ff00] text-xs opacity-70 ml-2">{aiLastAction}</span>
        )}
      </div>

      {/* Confidence panel — shown only in AI mode */}
      {aiMode && aiConfidence && (
        <div className="flex gap-4 mb-4 font-mono text-xs">
          {Object.entries(aiConfidence).map(([key, val]) => (
            <div key={key} className="bg-[#0f0f1e] border border-[#006600] px-3 py-1">
              <span className="text-[#006600]">{key.toUpperCase()} </span>
              <span className="text-[#00ff00]">{(val * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Meters Panel */}
      <div className="flex gap-6 mb-8">
        <div className="bg-[#0f0f1e] border-2 border-[#00ff00] p-4 font-mono">
          <div className="text-[#00ff00] text-sm mb-1">TEMPERATURE</div>
          <div className="text-[#00ff00] text-2xl">{temperature}°C</div>
        </div>
        <div className="bg-[#0f0f1e] border-2 border-[#00ff00] p-4 font-mono">
          <div className="text-[#00ff00] text-sm mb-1">HUMIDITY</div>
          <div className="text-[#00ff00] text-2xl">{humidity}%</div>
        </div>
        <div className="bg-[#0f0f1e] border-2 border-[#00ff00] p-4 font-mono">
          <div className="text-[#00ff00] text-sm mb-1">CO2 LEVEL</div>
          <div className="text-[#00ff00] text-2xl">{co2} ppm</div>
        </div>
      </div>

      {/* Blueprint Room */}
      <svg
        viewBox="0 0 600 600"
        className="w-full max-w-3xl border-2 border-[#00ff00] bg-[#0a0a14]"
        style={{ filter: 'contrast(1.1)' }}
      >
        {/* Grid Pattern */}
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#00ff00" strokeWidth="0.3" opacity="0.2"/>
          </pattern>
        </defs>
        <rect width="600" height="600" fill="url(#grid)" />

        {/* Room Walls */}
        <rect
          x="100"
          y="100"
          width="400"
          height="400"
          fill="none"
          stroke="#00ff00"
          strokeWidth="4"
        />

        {/* North Wall - Windows */}
        <g
          onClick={() => !aiMode && setWindowsOpen(!windowsOpen)}
          style={{ cursor: aiMode ? 'not-allowed' : 'pointer' }}
        >
          <rect
            x="250"
            y="100"
            width="100"
            height="4"
            fill={windowsOpen ? "#00ff00" : "#006600"}
            stroke="#00ff00"
            strokeWidth="2"
          />
          <line x1="250" y1="100" x2="250" y2="85" stroke="#00ff00" strokeWidth="1.5" />
          <line x1="300" y1="100" x2="300" y2="85" stroke="#00ff00" strokeWidth="1.5" />
          <line x1="350" y1="100" x2="350" y2="85" stroke="#00ff00" strokeWidth="1.5" />
          {windowsOpen && (
            <>
              <line x1="250" y1="100" x2="240" y2="75" stroke="#00ff00" strokeWidth="2" />
              <line x1="350" y1="100" x2="360" y2="75" stroke="#00ff00" strokeWidth="2" />
            </>
          )}
          <text x="300" y="70" fill="#00ff00" fontSize="10" textAnchor="middle" className="font-mono">
            WINDOWS {windowsOpen ? '(OPEN)' : '(CLOSED)'}
          </text>
        </g>

        {/* East Wall - Air Conditioner */}
        <g
          onClick={() => !aiMode && setAcOn(!acOn)}
          style={{ cursor: aiMode ? 'not-allowed' : 'pointer' }}
        >
          <rect
            x="496"
            y="250"
            width="4"
            height="100"
            fill={acOn ? "#00ccff" : "#003366"}
            stroke={acOn ? "#00ccff" : "#00ff00"}
            strokeWidth="2"
          />
          <rect
            x="505"
            y="270"
            width="30"
            height="60"
            fill={acOn ? "rgba(0, 204, 255, 0.2)" : "none"}
            stroke={acOn ? "#00ccff" : "#00ff00"}
            strokeWidth="1.5"
          />
          <line x1="510" y1="280" x2="530" y2="280" stroke={acOn ? "#00ccff" : "#00ff00"} strokeWidth="1" />
          <line x1="510" y1="290" x2="530" y2="290" stroke={acOn ? "#00ccff" : "#00ff00"} strokeWidth="1" />
          <line x1="510" y1="300" x2="530" y2="300" stroke={acOn ? "#00ccff" : "#00ff00"} strokeWidth="1" />
          <line x1="510" y1="310" x2="530" y2="310" stroke={acOn ? "#00ccff" : "#00ff00"} strokeWidth="1" />
          <line x1="510" y1="320" x2="530" y2="320" stroke={acOn ? "#00ccff" : "#00ff00"} strokeWidth="1" />
          <text x="550" y="305" fill={acOn ? "#00ccff" : "#00ff00"} fontSize="10" textAnchor="start" className="font-mono">
            A/C {acOn ? 'ON' : 'OFF'}
          </text>
        </g>

        {/* South Wall - Door */}
        <g
          onClick={() => setDoorOpen(!doorOpen)}
          style={{ cursor: 'pointer' }}
        >
          <rect
            x="260"
            y="496"
            width="80"
            height="4"
            fill={doorOpen ? "#00ff00" : "#006600"}
            stroke="#00ff00"
            strokeWidth="2"
          />
          {doorOpen ? (
            <path
              d="M 340 500 Q 360 520 340 540"
              fill="none"
              stroke="#00ff00"
              strokeWidth="2"
            />
          ) : (
            <line x1="300" y1="500" x2="300" y2="515" stroke="#00ff00" strokeWidth="1.5" />
          )}
          <text x="300" y="560" fill="#00ff00" fontSize="10" textAnchor="middle" className="font-mono">
            DOOR {doorOpen ? '(OPEN)' : '(CLOSED)'}
          </text>
        </g>

        {/* West Wall - Heater */}
        <g
          onClick={() => !aiMode && setHeaterOn(!heaterOn)}
          style={{ cursor: aiMode ? 'not-allowed' : 'pointer' }}
        >
          <rect
            x="100"
            y="250"
            width="4"
            height="100"
            fill={heaterOn ? "#ff4444" : "#660000"}
            stroke={heaterOn ? "#ff4444" : "#00ff00"}
            strokeWidth="2"
          />
          <rect
            x="65"
            y="270"
            width="30"
            height="60"
            fill={heaterOn ? "rgba(255, 68, 68, 0.2)" : "none"}
            stroke={heaterOn ? "#ff4444" : "#00ff00"}
            strokeWidth="1.5"
          />
          {heaterOn && (
            <>
              <circle cx="80" cy="290" r="3" fill="#ff4444" opacity="0.8" />
              <circle cx="80" cy="300" r="3" fill="#ff4444" opacity="0.6" />
              <circle cx="80" cy="310" r="3" fill="#ff4444" opacity="0.8" />
            </>
          )}
          <text x="50" y="305" fill={heaterOn ? "#ff4444" : "#00ff00"} fontSize="10" textAnchor="end" className="font-mono">
            HEATER {heaterOn ? 'ON' : 'OFF'}
          </text>
        </g>

        {/* Center - Baby Crib */}
        <g>
          <rect
            x="250"
            y="250"
            width="100"
            height="100"
            fill="none"
            stroke="#00ff00"
            strokeWidth="2"
          />
          <line x1="250" y1="260" x2="350" y2="260" stroke="#00ff00" strokeWidth="1" />
          <line x1="250" y1="270" x2="350" y2="270" stroke="#00ff00" strokeWidth="1" />
          <line x1="250" y1="340" x2="350" y2="340" stroke="#00ff00" strokeWidth="1" />
          <line x1="260" y1="250" x2="260" y2="350" stroke="#00ff00" strokeWidth="1" />
          <line x1="270" y1="250" x2="270" y2="350" stroke="#00ff00" strokeWidth="1" />
          <line x1="330" y1="250" x2="330" y2="350" stroke="#00ff00" strokeWidth="1" />
          <line x1="340" y1="250" x2="340" y2="350" stroke="#00ff00" strokeWidth="1" />
          <ellipse cx="300" cy="300" rx="25" ry="15" fill="none" stroke="#00ff00" strokeWidth="1.5" />
          <text x="300" y="380" fill="#00ff00" fontSize="10" textAnchor="middle" className="font-mono">
            CRIB
          </text>
        </g>

        {/* Dimension Lines */}
        <text x="300" y="130" fill="#00ff00" fontSize="8" textAnchor="middle" className="font-mono">N</text>
        <text x="300" y="580" fill="#00ff00" fontSize="8" textAnchor="middle" className="font-mono">S</text>
        <text x="70" y="305" fill="#00ff00" fontSize="8" textAnchor="middle" className="font-mono">W</text>
        <text x="530" y="305" fill="#00ff00" fontSize="8" textAnchor="middle" className="font-mono">E</text>
      </svg>

      {/* Instructions */}
      <div className="mt-6 text-[#00ff00] font-mono text-sm text-center max-w-2xl">
        <p>INTERACTIVE ROOM CONTROL SYSTEM</p>
        <p className="text-xs mt-2 opacity-70">
          Click on any element to interact: Door | Windows | Heater | Air Conditioner
        </p>
      </div>
    </div>
  );
}