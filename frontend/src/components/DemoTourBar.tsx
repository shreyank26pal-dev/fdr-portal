import React, { useState } from 'react';
import { Sparkles, Play, X, ChevronRight } from 'lucide-react';
import { ActiveTab } from './Header';

interface DemoTourBarProps {
  onClose: () => void;
  onRunScene: (email: string, tab: ActiveTab) => Promise<void>;
}

const SCENES = [
  {
    id: 1,
    time: '0:00–0:45',
    title: 'Scene 1: Executive Risk & Concentration',
    desc: 'Logs in as Scrutiny Officer (`officer@aicte-demo.in`) to inspect KPIs, bank exposure, and predicted late renewals.',
    email: 'officer@aicte-demo.in',
    tab: 'officer' as ActiveTab,
  },
  {
    id: 2,
    time: '0:45–2:00',
    title: 'Scene 2: Submission + Live OCR Auto-Fill',
    desc: 'Logs in as `college1@aicte-demo.in` to load `fdr_demo_correct.pdf`, auto-fill via OCR, and run Point-of-Entry cross-check.',
    email: 'college1@aicte-demo.in',
    tab: 'institution' as ActiveTab,
  },
  {
    id: 3,
    time: '2:00–2:45',
    title: 'Scene 3: Forgery Catch (R15 & R09)',
    desc: 'Inspects Dual-Truth Split-Screen where Words-vs-Figures tampering (R15) and Cross-Institution Duplicate (R09) are flagged.',
    email: 'officer@aicte-demo.in',
    tab: 'split' as ActiveTab,
  },
  {
    id: 4,
    time: '2:45–3:30',
    title: 'Scene 4: Blind Bank Confirmation',
    desc: 'Opens Blind Bank Portal (`bank.sbi@aicte-demo.in`) where declared values are hidden and bank enters CBS values blind.',
    email: 'bank.sbi@aicte-demo.in',
    tab: 'bank' as ActiveTab,
  },
  {
    id: 5,
    time: '3:30–4:15',
    title: 'Scene 5: Silent Encashment & Time-Travel',
    desc: 'Switches to `admin@aicte-demo.in` to fast-forward +66/+8 days and simulate mid-tenure premature encashment.',
    email: 'admin@aicte-demo.in',
    tab: 'admin' as ActiveTab,
  },
  {
    id: 6,
    time: '4:15–5:15',
    title: 'Scene 6: Institution Lock (HTTP 423)',
    desc: 'Switches to `college5@aicte-demo.in` to show overdue renewal lock blocking fresh FDRs until renewed.',
    email: 'college5@aicte-demo.in',
    tab: 'institution' as ActiveTab,
  },
  {
    id: 7,
    time: '5:15–6:00',
    title: 'Scene 7: Two-Person Release & Audit Chain',
    desc: 'Switches to `auditor@aicte-demo.in` / `approver@aicte-demo.in` to verify SHA-256 audit chain and Discharge Order PDF.',
    email: 'auditor@aicte-demo.in',
    tab: 'admin' as ActiveTab,
  },
];

export const DemoTourBar: React.FC<DemoTourBarProps> = ({ onClose, onRunScene }) => {
  const [activeScene, setActiveScene] = useState<number>(1);

  const current = SCENES.find((s) => s.id === activeScene) || SCENES[0];

  return (
    <div className="bg-gradient-to-r from-amber-500 via-amber-400 to-orange-400 text-slate-950 border-b border-amber-600 shadow-md">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-3 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-slate-950" />
            <span className="font-display font-extrabold text-xs sm:text-sm uppercase tracking-wide">
              Interactive 6-Minute Hackathon Judge Walkthrough (7 Scenes from README)
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-950/15 hover:bg-slate-950/25 text-xs font-bold cursor-pointer"
          >
            <X className="w-3.5 h-3.5" /> Hide Tour
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5">
          {SCENES.map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => {
                setActiveScene(sc.id);
                onRunScene(sc.email, sc.tab);
              }}
              className={`p-2 rounded-xl text-left transition cursor-pointer border ${
                activeScene === sc.id
                  ? 'bg-[#0F2547] text-white border-[#0F2547] shadow-xs'
                  : 'bg-white/80 hover:bg-white text-slate-900 border-amber-600/30'
              }`}
            >
              <div className="font-mono text-[10px] opacity-80">{sc.time}</div>
              <div className="font-bold text-[11px] leading-snug mt-0.5">{sc.title}</div>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 bg-white/90 rounded-xl px-3.5 py-2 text-xs">
          <div>
            <span className="font-bold text-[#0F2547]">{current.title}:</span>{' '}
            <span className="text-slate-700">{current.desc}</span>
          </div>
          <button
            type="button"
            onClick={() => onRunScene(current.email, current.tab)}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-[#0F2547] text-amber-300 font-bold cursor-pointer"
          >
            <Play className="w-3 h-3" /> Jump to Scene {current.id} <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
