<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Vehicle Intelligence - Import Cars</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&amp;family=Space+Grotesk:wght@300;400;500;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    colors: {
                        "on-secondary": "#003919",
                        "surface-container": "#171f33",
                        "on-error-container": "#ffdad6",
                        "on-background": "#dae2fd",
                        "on-error": "#690005",
                        "on-primary-container": "#00285d",
                        "outline-variant": "#424754",
                        "surface-tint": "#adc6ff",
                        "surface": "#0b1326",
                        "secondary-container": "#00b55d",
                        "error-container": "#93000a",
                        "on-tertiary-fixed": "#261a00",
                        "on-surface-variant": "#c2c6d6",
                        "surface-container-high": "#222a3d",
                        "on-tertiary-container": "#372700",
                        "inverse-primary": "#005ac2",
                        "primary-fixed-dim": "#adc6ff",
                        "tertiary": "#f9bd22",
                        "inverse-surface": "#dae2fd",
                        "secondary-fixed": "#6dfe9c",
                        "on-primary-fixed-variant": "#004395",
                        "surface-container-lowest": "#060e20",
                        "on-secondary-fixed": "#00210c",
                        "on-secondary-container": "#003e1c",
                        "secondary": "#4de082",
                        "inverse-on-surface": "#283044",
                        "primary-fixed": "#d8e2ff",
                        "surface-variant": "#2d3449",
                        "error": "#ffb4ab",
                        "on-primary-fixed": "#001a42",
                        "on-secondary-fixed-variant": "#005227",
                        "on-tertiary-fixed-variant": "#5c4300",
                        "background": "#0b1326",
                        "tertiary-fixed": "#ffdf9f",
                        "surface-container-low": "#131b2e",
                        "secondary-fixed-dim": "#4de082",
                        "surface-dim": "#0b1326",
                        "primary-container": "#4d8eff",
                        "surface-container-highest": "#2d3449",
                        "surface-bright": "#31394d",
                        "on-surface": "#dae2fd",
                        "on-tertiary": "#402d00",
                        "on-primary": "#002e6a",
                        "outline": "#8c909f",
                        "primary": "#adc6ff",
                        "tertiary-fixed-dim": "#f9bd22",
                        "tertiary-container": "#b88900"
                    },
                    fontFamily: {
                        "headline": ["Inter"],
                        "body": ["Inter"],
                        "label": ["Space Grotesk"]
                    },
                    borderRadius: {"DEFAULT": "0rem", "lg": "0rem", "xl": "0rem", "full": "9999px"},
                },
            },
        }
    </script>
<style>
        .material-symbols-outlined {
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
            vertical-align: middle;
        }
        body {
            background-color: #0b1326;
            color: #dae2fd;
        }
        ::-webkit-scrollbar {
            width: 4px;
        }
        ::-webkit-scrollbar-track {
            background: #2d3449;
        }
        ::-webkit-scrollbar-thumb {
            background: #adc6ff;
        }
    </style>
</head>
<body class="overflow-hidden font-body">
<!-- Background Content Simulation (Dashboard) -->
<div class="fixed inset-0 grid grid-cols-[256px_1fr] pointer-events-none opacity-40">
<!-- Sidebar Shell -->
<aside class="bg-[#0b1326] border-r border-[#424754]/15 p-6 flex flex-col gap-8">
<div class="h-8 w-32 bg-surface-container-highest"></div>
<div class="space-y-4">
<div class="h-10 w-full bg-surface-container-highest"></div>
<div class="h-10 w-full bg-surface-container-highest"></div>
<div class="h-10 w-full bg-surface-container-highest"></div>
</div>
</aside>
<!-- Main Content Shell -->
<main class="p-8 space-y-8">
<div class="h-12 w-64 bg-surface-container-highest"></div>
<div class="grid grid-cols-3 gap-6">
<div class="h-48 bg-surface-container-highest"></div>
<div class="h-48 bg-surface-container-highest"></div>
<div class="h-48 bg-surface-container-highest"></div>
</div>
<div class="h-96 w-full bg-surface-container-highest"></div>
</main>
</div>
<!-- Navigation Drawer Overlay -->
<div class="fixed inset-0 bg-surface-container-lowest/60 backdrop-blur-sm z-50"></div>
<!-- NavigationDrawer (The "Semantic Shell") -->
<div class="fixed right-0 top-0 h-screen w-[500px] bg-[#131b2e]/90 backdrop-blur-xl border-l border-[#424754]/30 shadow-[-20px_0_40px_rgba(6,14,32,0.7)] flex flex-col z-[60] overflow-y-auto">
<!-- Header -->
<div class="p-6 pb-4 flex justify-between items-start border-b border-[#424754]/15">
<div>
<h1 class="font-headline font-black text-xl tracking-tighter uppercase text-on-surface">BMW M3 Competition (G80)</h1>
<p class="font-label text-xs tracking-widest text-primary uppercase opacity-70">Opportunity #042</p>
</div>
<button class="text-on-surface-variant hover:text-white transition-colors">
<span class="material-symbols-outlined">close</span>
</button>
</div>
<!-- Content Canvas -->
<div class="flex-1 p-6 space-y-8">
<!-- Hero Vehicle Image -->
<div class="relative group h-56 w-full bg-surface-container-highest overflow-hidden">
<img alt="BMW M3 Competition G80 in frozen dark grey" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" data-alt="front three-quarter view of a BMW M3 Competition G80 in frozen dark grey parked in a high-tech modern architectural garage with linear neon lighting" src="https://lh3.googleusercontent.com/aida-public/AB6AXuD0x_pMma5WkU095RU-Ll7-pR5ZWdQ1E7rPoRGuYhM8asVd3Eo2K0PEzX6Oo01JGoOrCVCrYWQazW3Y_Aq-GAHKDkXvxR1MY7F2eQTVG7aMAFj4mQmpWTU_i9qbVCv_kg_IC-bRbSyQEk9fCAYxOz3YNBcbyHx0iiIwJ9jtvNvX0dFng_MhfHnBxYpjPLiTCTewMC68K7BTXpQgMQnnorxlNKuHYXbnC087zLc9BSCXDJBCijvGSDlnsG30RpVRVmr_kwVZc7DMmPo"/>
<div class="absolute inset-0 bg-gradient-to-t from-surface-container-low via-transparent to-transparent"></div>
<div class="absolute bottom-4 left-4 right-4 flex justify-between items-end">
<div class="bg-primary/10 backdrop-blur-md border border-primary/20 p-2">
<span class="font-label text-[10px] uppercase text-primary tracking-widest block">Confidence</span>
<span class="font-headline font-bold text-sm">High (Inferred Exact)</span>
</div>
</div>
</div>
<!-- Specs Grid -->
<div class="grid grid-cols-4 gap-px bg-[#424754]/20 border border-[#424754]/20">
<div class="bg-surface-container-low p-3">
<span class="font-label text-[10px] uppercase text-on-surface-variant tracking-wider block mb-1">Year</span>
<span class="font-headline font-bold text-sm">2021</span>
</div>
<div class="bg-surface-container-low p-3">
<span class="font-label text-[10px] uppercase text-on-surface-variant tracking-wider block mb-1">Mileage</span>
<span class="font-headline font-bold text-sm">28k km</span>
</div>
<div class="bg-surface-container-low p-3">
<span class="font-label text-[10px] uppercase text-on-surface-variant tracking-wider block mb-1">Power</span>
<span class="font-headline font-bold text-sm">510hp</span>
</div>
<div class="bg-surface-container-low p-3">
<span class="font-label text-[10px] uppercase text-on-surface-variant tracking-wider block mb-1">Fuel</span>
<span class="font-headline font-bold text-sm">Petrol</span>
</div>
</div>
<!-- Primary Action -->
<button class="w-full bg-primary-container text-on-primary-container font-headline font-extrabold uppercase py-4 tracking-tighter hover:bg-primary transition-all active:scale-[0.98] flex items-center justify-center gap-2 group">
                View Listing on Mobile.de
                <span class="material-symbols-outlined text-lg transition-transform group-hover:translate-x-1">open_in_new</span>
</button>
<!-- Cost Breakdown -->
<div class="space-y-4">
<h3 class="font-headline font-bold text-xs uppercase tracking-[0.2em] text-on-surface-variant flex items-center gap-2">
<span class="material-symbols-outlined text-sm">account_balance</span> Import Cost Analysis
                </h3>
<div class="space-y-1">
<div class="flex justify-between items-center p-3 bg-surface-container-low/50">
<span class="font-body text-sm text-on-surface-variant">DE Purchase Price</span>
<span class="font-headline font-bold text-sm">82,500€</span>
</div>
<div class="flex justify-between items-center p-3 bg-surface-container-low/50">
<span class="font-body text-sm text-on-surface-variant">German VAT (19%) Deductible</span>
<span class="font-headline font-bold text-sm text-secondary">-13,172€</span>
</div>
<div class="flex justify-between items-center p-3 bg-surface-container-low/50">
<div class="flex items-center gap-2">
<span class="font-body text-sm text-on-surface-variant">ES Registration Tax</span>
<span class="material-symbols-outlined text-xs text-tertiary">info</span>
</div>
<span class="font-headline font-bold text-sm text-error">+7,400€</span>
</div>
<div class="flex justify-between items-center p-3 bg-surface-container-low/50">
<span class="font-body text-sm text-on-surface-variant">Transport &amp; Paperwork</span>
<span class="font-headline font-bold text-sm text-error">+1,200€</span>
</div>
<div class="flex justify-between items-center p-4 bg-surface-container-highest border-l-2 border-primary mt-2">
<span class="font-headline font-bold text-sm uppercase">Total Cost to Spain</span>
<span class="font-headline font-black text-lg text-primary">77,928€</span>
</div>
</div>
<div class="p-4 bg-secondary/5 border border-secondary/20 flex items-center justify-between">
<div>
<span class="font-label text-[10px] uppercase text-secondary tracking-widest block mb-1">Expected Profit Margin</span>
<div class="flex items-baseline gap-2">
<span class="font-headline font-black text-2xl text-secondary">14,072€</span>
<span class="font-label text-xs text-secondary/60">vs 92,000€ Median</span>
</div>
</div>
<span class="material-symbols-outlined text-secondary text-4xl" style="font-variation-settings: 'FILL' 1;">trending_up</span>
</div>
</div>
<!-- Comparables -->
<div class="space-y-4">
<h3 class="font-headline font-bold text-xs uppercase tracking-[0.2em] text-on-surface-variant flex items-center gap-2">
<span class="material-symbols-outlined text-sm">compare_arrows</span> Local Market (Coches.net)
                </h3>
<div class="space-y-3">
<!-- Comparable Item -->
<div class="group flex items-center gap-4 p-3 bg-surface-container-low/30 hover:bg-surface-container-high transition-colors">
<div class="w-16 h-12 bg-surface-container-highest overflow-hidden border border-[#424754]/30">
<img alt="BMW M3 G80 profile" class="w-full h-full object-cover" data-alt="side profile of a BMW M3 G80 in portimao blue with shadowline pack, technical lighting" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCicLkXsXOsqtQv2-_spLhBA8lv5dmqSIKCUDoqCrNLfVlhIT0L4jwZmduL3SgwwsZcylEpFsW65Ky5GppyDppweS0fQ3Rs5gwXP8HPsIkcFhmP6vja_3jtDlPmWFh0GXaxLQ8yjAg6Xwra20vZqOpdhb02LGD8p3TNzRVgr6420mjuoroO2OacTtTlnBkgmbCwu6WC2EAmIPPdaLwZIplNnsXBlS5VXj8VasNPIxb8ItYG26rTZbvGu3J_8jm8Tjl3HeHdZIFcXz4"/>
</div>
<div class="flex-1">
<div class="flex justify-between">
<span class="font-headline font-bold text-xs">BMW M3 Comp. (2022)</span>
<span class="font-headline font-bold text-xs">94,900€</span>
</div>
<div class="flex items-center gap-3 mt-1">
<span class="font-label text-[9px] text-on-surface-variant">15,000 KM</span>
<div class="px-1.5 py-0.5 bg-secondary-container text-on-secondary text-[8px] font-black uppercase tracking-tighter">Exact Match</div>
</div>
</div>
</div>
<!-- Comparable Item -->
<div class="group flex items-center gap-4 p-3 bg-surface-container-low/30 hover:bg-surface-container-high transition-colors">
<div class="w-16 h-12 bg-surface-container-highest overflow-hidden border border-[#424754]/30">
<img alt="BMW M3 G80 rear" class="w-full h-full object-cover" data-alt="rear view of a BMW M3 G80 in brooklyn grey showing quad exhausts and carbon diffuser" src="https://lh3.googleusercontent.com/aida-public/AB6AXuC6A3reo0d1I3mOQ6Hx_7imtQdwmOdyhNyXUew8--LUAnjmArwm-YsNmoW7updxAewPZlMPCrnSZIdMa9r3232i4rNYT-z0feeCXbN75aVxocqKggyhn18L8CTXA4IpWZpYT1044WdY8x1WuAGn6LI8cBtgjeRERSFhu5P1U2w5a8OjlPBasCMi1o_gLgJ5RQQsJsEF_5ffQ0I8XuJvGRPG2agfIQ5kDGcwIv-bWlGKl_Mw75XB1i_OlXha76adz_eKIuH4YhuVkX8"/>
</div>
<div class="flex-1">
<div class="flex justify-between">
<span class="font-headline font-bold text-xs">BMW M3 Sedan (2021)</span>
<span class="font-headline font-bold text-xs">89,500€</span>
</div>
<div class="flex items-center gap-3 mt-1">
<span class="font-label text-[9px] text-on-surface-variant">42,000 KM</span>
<div class="px-1.5 py-0.5 bg-tertiary-container text-on-tertiary text-[8px] font-black uppercase tracking-tighter">Near Match</div>
</div>
</div>
</div>
</div>
</div>
<!-- Intelligence Logic Info -->
<div class="p-4 bg-surface-container-highest/40 border-l-2 border-outline-variant">
<div class="flex gap-3">
<span class="material-symbols-outlined text-primary text-lg">psychology</span>
<div class="space-y-1">
<span class="font-headline font-bold text-[10px] uppercase tracking-wider text-primary">Intelligence Logic</span>
<p class="font-body text-[11px] text-on-surface-variant leading-relaxed">
<span class="text-white font-bold">Exact Match</span> requires matching engine code, trim line, and &lt;10k km mileage variance. 
                            <span class="text-white font-bold">Near Match</span> accounts for cosmetic trim differences or &gt;20k km mileage spread. CO2 enrichment verified against EU DB.
                        </p>
</div>
</div>
</div>
</div>
<!-- Footer Actions -->
<div class="p-6 border-t border-[#424754]/15 flex gap-3 bg-surface-container-low">
<button class="flex-1 border border-outline-variant hover:bg-surface-container-highest text-on-surface-variant font-headline font-bold text-xs py-3 uppercase tracking-tighter transition-all flex items-center justify-center gap-2">
<span class="material-symbols-outlined text-sm">download</span>
                Export Analysis
            </button>
<button class="flex-1 bg-surface-container-highest text-on-surface font-headline font-bold text-xs py-3 uppercase tracking-tighter transition-all flex items-center justify-center gap-2">
<span class="material-symbols-outlined text-sm">bookmark</span>
                Save Report
            </button>
</div>
</div>
</body></html>