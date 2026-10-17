import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function iconProps(size: IconProps["width"]): IconProps {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
}

export function CropIcon({ width = 24, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <path d="M7 3v14a2 2 0 0 0 2 2h12" />
      <path d="M3 7h12a2 2 0 0 1 2 2v12" />
    </svg>
  );
}

export function RotateIcon({ width = 24, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <path d="M20 7v5h-5" />
      <path d="M19 12a7 7 0 1 0-2 5" />
    </svg>
  );
}

export function FilterIcon({ width = 24, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 4a8 8 0 0 0 0 16V4Z" fill="currentColor" stroke="none" opacity="0.45" />
      <path d="M12 4v16" />
    </svg>
  );
}

export function CaptionIcon({ width = 24, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <path d="M5 18 9.2 6h1.6L15 18M6.4 14h7.2" />
      <path d="M16 10h3M16 14h3M16 18h3" />
    </svg>
  );
}

export function JpegIcon({ width = 24, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </svg>
  );
}

export function RestyleIcon({ width = 24, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <path d="m12 3 1.25 3.75L17 8l-3.75 1.25L12 13l-1.25-3.75L7 8l3.75-1.25L12 3Z" />
      <path d="m18.5 14 .75 2.25 2.25.75-2.25.75L18.5 20l-.75-2.25L15.5 17l2.25-.75.75-2.25Z" />
      <path d="m5.5 12 .65 1.85L8 14.5l-1.85.65L5.5 17l-.65-1.85L3 14.5l1.85-.65L5.5 12Z" />
    </svg>
  );
}

export function InfoIcon({ width = 16, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7h.01" />
    </svg>
  );
}

export function PencilIcon({ width = 16, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <path d="m14.5 5.5 4 4M4 20l3.5-.75L19 7.75a2.12 2.12 0 0 0-3-3L4.75 16 4 20Z" />
    </svg>
  );
}

export function NetworkIcon({ width = 16, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <circle cx="12" cy="5" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="18" r="2.5" />
      <path d="m11 7.3-3.8 8.4M13 7.3l3.8 8.4M8.5 18h7" />
    </svg>
  );
}

export function BriefcaseIcon({ width = 16, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <rect x="3" y="7" width="18" height="12" rx="2" />
      <path d="M9 7V5h6v2M3 12h18M10 12v2h4v-2" />
    </svg>
  );
}

export function TextLinesIcon({ width = 16, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <path d="M5 6h14M5 10h14M5 14h10M5 18h12" />
    </svg>
  );
}

export function CompareIcon({ width = 16, ...props }: IconProps) {
  return (
    <svg {...iconProps(width)} {...props}>
      <rect x="3" y="5" width="7" height="11" rx="1.5" />
      <rect x="14" y="8" width="7" height="11" rx="1.5" />
      <path d="m10 10 4 4M13 11l1 3-3-1" />
    </svg>
  );
}
