import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface Initial3DLoaderProps {
  onComplete: () => void;
}

export const Initial3DLoader: React.FC<Initial3DLoaderProps> = ({ onComplete }) => {
  const [progress, setProgress] = useState(0);
  const [logIndex, setLogIndex] = useState(0);

  const TELEMETRY_LOGS = [
    'MOUNTING ISOLATED DOCUMENT PARTITIONS...',
    'VALIDATING CRYPTOGRAPHIC INTEGRITY...',
    'SYNCHRONIZING 1,536-DIM VECTOR INDEX...',
    'ATTESTING ROLE-BASED ACCESS BOUNDARIES...',
    'SYSTEM ONLINE // GROUNDED KNOWLEDGE READY',
  ];

  useEffect(() => {
    const startTime = performance.now();
    const duration = 1850; // Calibrated 1.85s timing for a crisp, high-end experience

    let animationFrameId: number;

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const rawProgress = Math.min(elapsed / duration, 1);

      // Smooth custom ease-out curve (cubic-out)
      const current = Math.round((1 - Math.pow(1 - rawProgress, 3)) * 100);
      setProgress(current);

      if (current < 20) setLogIndex(0);
      else if (current < 45) setLogIndex(1);
      else if (current < 72) setLogIndex(2);
      else if (current < 92) setLogIndex(3);
      else setLogIndex(4);

      if (rawProgress < 1) {
        animationFrameId = requestAnimationFrame(tick);
      } else {
        setTimeout(() => {
          onComplete();
        }, 220);
      }
    };

    animationFrameId = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(animationFrameId);
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{
        opacity: 0,
        scale: 1.015,
        filter: 'blur(3px)',
        transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
      }}
      className="fixed inset-0 z-[9999] bg-[#0A0908] text-[#F5F1EB] flex flex-col justify-between p-6 sm:p-10 select-none overflow-hidden font-sans"
    >
      {/* Precision CAD / Atmospheric Background Grid */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Sub-pixel Vector Dot Matrix */}
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `radial-gradient(circle, #ffffff 1px, transparent 1px)`,
            backgroundSize: '24px 24px',
          }}
        />
        {/* Soft Radial Vignette & Warm Burnt Orange Glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[650px] h-[650px] bg-gradient-radial from-[#F0652F]/12 via-[#F0652F]/3 to-transparent blur-[120px] rounded-full pointer-events-none" />
      </div>

      {/* Top HUD Telemetry Bar */}
      <div className="relative z-10 max-w-6xl w-full mx-auto flex items-center justify-between text-[11px] font-mono tracking-wider text-white/40 border-b border-white/[0.07] pb-4">
        <div className="flex items-center gap-3">
          <span className="inline-block h-2 w-2 rounded-full bg-[#F0652F] animate-pulse" />
          <span className="font-semibold text-white/70">ENTERPRISE_QUERY // SECURE_ENCLAVE</span>
          <span className="hidden sm:inline text-white/20">|</span>
          <span className="hidden sm:inline">SHA256_VERIFIED</span>
        </div>

        <div className="flex items-center gap-4 font-semibold text-white/60">
          <span className="hidden sm:inline">TLS 1.3 • AES-256</span>
          <span className="px-2 py-0.5 rounded bg-white/[0.05] border border-white/[0.08] text-[#F0652F]">
            PARTITION_0x88F2
          </span>
        </div>
      </div>

      {/* Centerpiece: Authentic High-Precision Isometric Vector Wireframe */}
      <div className="relative z-10 flex flex-col items-center justify-center my-auto">
        <div className="relative w-72 h-72 flex items-center justify-center">
          {/* Outer Rotating Calibration Reticle */}
          <motion.svg
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 24, ease: 'linear' }}
            className="absolute inset-0 w-full h-full pointer-events-none opacity-25"
            viewBox="0 0 288 288"
          >
            <circle
              cx="144"
              cy="144"
              r="138"
              fill="none"
              stroke="#F0652F"
              strokeWidth="1"
              strokeDasharray="4 8"
            />
            <circle
              cx="144"
              cy="144"
              r="112"
              fill="none"
              stroke="white"
              strokeWidth="0.75"
              strokeDasharray="1 16"
            />
          </motion.svg>

          {/* Counter-Rotating Degree Marks */}
          <motion.svg
            animate={{ rotate: -360 }}
            transition={{ repeat: Infinity, duration: 32, ease: 'linear' }}
            className="absolute inset-6 w-60 h-60 pointer-events-none opacity-30"
            viewBox="0 0 240 240"
          >
            <line x1="120" y1="4" x2="120" y2="12" stroke="#F0652F" strokeWidth="1.5" />
            <line x1="120" y1="228" x2="120" y2="236" stroke="#F0652F" strokeWidth="1.5" />
            <line x1="4" y1="120" x2="12" y2="120" stroke="#F0652F" strokeWidth="1.5" />
            <line x1="228" y1="120" x2="236" y2="120" stroke="#F0652F" strokeWidth="1.5" />
          </motion.svg>

          {/* 3D Isometric Precision Geometric Prism Wireframe */}
          <motion.div
            animate={{
              rotateY: [0, 180, 360],
              rotateX: [22, 14, 22],
            }}
            transition={{
              rotateY: { repeat: Infinity, duration: 16, ease: 'linear' },
              rotateX: { repeat: Infinity, duration: 6, ease: 'easeInOut' },
            }}
            style={{
              perspective: '800px',
              transformStyle: 'preserve-3d',
            }}
            className="relative w-36 h-36 flex items-center justify-center"
          >
            {/* Precision Vector Isometric Hexagon / Cube Projection */}
            <svg
              className="w-36 h-36 drop-shadow-[0_0_20px_rgba(240,101,47,0.35)]"
              viewBox="0 0 100 100"
              fill="none"
            >
              <defs>
                <linearGradient id="topFace" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#F0652F" stopOpacity="0.12" />
                </linearGradient>
                <linearGradient id="leftFace" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F0652F" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#F0652F" stopOpacity="0.04" />
                </linearGradient>
                <linearGradient id="rightFace" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#F0652F" stopOpacity="0.02" />
                </linearGradient>
                <linearGradient id="laserStroke" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#ffffff" />
                  <stop offset="50%" stopColor="#F0652F" />
                  <stop offset="100%" stopColor="#EA580C" />
                </linearGradient>
              </defs>

              {/* Isometric Top Diamond */}
              <polygon
                points="50,15 85,32 50,50 15,32"
                fill="url(#topFace)"
                stroke="url(#laserStroke)"
                strokeWidth="1.2"
              />

              {/* Isometric Left Parallelogram */}
              <polygon
                points="15,32 50,50 50,85 15,67"
                fill="url(#leftFace)"
                stroke="#F0652F"
                strokeWidth="1.2"
                strokeOpacity="0.8"
              />

              {/* Isometric Right Parallelogram */}
              <polygon
                points="50,50 85,32 85,67 50,85"
                fill="url(#rightFace)"
                stroke="#F0652F"
                strokeWidth="1.2"
                strokeOpacity="0.8"
              />

              {/* Internal Isometric Vector Axes */}
              <line x1="50" y1="50" x2="50" y2="85" stroke="#ffffff" strokeWidth="1.2" strokeOpacity="0.9" />
              <line x1="50" y1="50" x2="15" y2="32" stroke="#ffffff" strokeWidth="1.2" strokeOpacity="0.5" />
              <line x1="50" y1="50" x2="85" y2="32" stroke="#ffffff" strokeWidth="1.2" strokeOpacity="0.5" />

              {/* Center Core Floating Singularity */}
              <circle cx="50" cy="50" r="3" fill="#ffffff" className="drop-shadow-[0_0_8px_#ffffff]" />
              <circle cx="50" cy="15" r="1.5" fill="#F0652F" />
              <circle cx="85" cy="32" r="1.5" fill="#F0652F" />
              <circle cx="15" cy="32" r="1.5" fill="#F0652F" />
              <circle cx="50" cy="85" r="1.5" fill="#F0652F" />
              <circle cx="15" cy="67" r="1.5" fill="#F0652F" />
              <circle cx="85" cy="67" r="1.5" fill="#F0652F" />
            </svg>
          </motion.div>
        </div>

        {/* Brand Typographic Identity */}
        <div className="mt-6 text-center space-y-2">
          <div className="text-[11px] uppercase tracking-[0.32em] font-mono font-semibold text-[#F0652F]">
            Enterprise Knowledge Engine
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white/95">
            EnterpriseQuery
          </h1>
        </div>

        {/* Industry-Grade Minimalist Linear Progress Gauge */}
        <div className="mt-6 w-64 space-y-2.5">
          <div className="h-[2px] w-full bg-white/[0.08] rounded-full overflow-hidden relative">
            <motion.div
              className="h-full bg-gradient-to-r from-[#EA580C] via-[#F0652F] to-white shadow-[0_0_12px_#F0652F]"
              style={{ width: `${progress}%` }}
              transition={{ ease: 'linear' }}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono text-white/45">
            <span className="truncate pr-2 font-medium">{TELEMETRY_LOGS[logIndex]}</span>
            <span className="font-bold text-white/90 tabular-nums">
              {progress.toString().padStart(2, '0')}%
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Status Ticker */}
      <div className="relative z-10 max-w-6xl w-full mx-auto flex flex-col sm:flex-row items-center justify-between text-[10px] font-mono text-white/35 gap-2 border-t border-white/[0.07] pt-4">
        <div className="flex items-center gap-3">
          <span>LATENCY: 12ms</span>
          <span>•</span>
          <span>VECTOR_DIM: 1536</span>
          <span>•</span>
          <span>ENCLAVE: ACTIVE</span>
        </div>

        <span>© 2026 ENTERPRISEQUERY • GROUNDED CITATION KERNEL</span>
      </div>
    </motion.div>
  );
};