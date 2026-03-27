<!DOCTYPE html>

<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Import Cars | Market Intelligence Terminal</title>
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
            borderRadius: {"DEFAULT": "0px", "lg": "0px", "xl": "0px", "full": "9999px"},
          },
        },
      }
    </script>
<style>
        body {
            background-color: #0b1326;
            color: #dae2fd;
            font-family: 'Inter', sans-serif;
            overflow-x: hidden;
        }
        .material-symbols-outlined {
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
            vertical-align: middle;
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #2d3449; }
        ::-webkit-scrollbar-thumb { background: #adc6ff; }
        .sharp-edge { border-radius: 0px !important; }
    </style>
</head>
<body class="dark bg-surface text-on-surface font-body">
<!-- TopNavBar -->
<header class="bg-[#0b1326] text-[#adc6ff] font-['Inter'] font-bold tracking-tight text-sm docked full-width top-0 z-50 flex justify-between items-center w-full px-6 h-16 fixed">
<div class="flex items-center gap-8">
<div class="text-xl font-black tracking-tighter text-[#adc6ff] uppercase">Import Cars</div>
<nav class="hidden md:flex items-center gap-6">
<a class="text-[#adc6ff] border-b-2 border-[#adc6ff] pb-1 h-16 flex items-center" href="#">Market Intelligence</a>
<a class="text-[#94a3b8] hover:text-[#f8fafc] h-16 flex items-center transition-colors duration-150" href="#">Comparisons</a>
<a class="text-[#94a3b8] hover:text-[#f8fafc] h-16 flex items-center transition-colors duration-150" href="#">Inventory</a>
<a class="text-[#94a3b8] hover:text-[#f8fafc] h-16 flex items-center transition-colors duration-150" href="#">Reports</a>
</nav>
</div>
<div class="flex items-center gap-4">
<button class="bg-primary-container text-on-primary-container px-4 py-2 font-bold sharp-edge hover:bg-primary-fixed transition-all active:scale-95 duration-75">
                Run Comparison
            </button>
<div class="flex items-center gap-3 ml-4">
<span class="material-symbols-outlined text-[#94a3b8] cursor-pointer hover:text-[#f8fafc]" data-icon="download">download</span>
<span class="material-symbols-outlined text-[#94a3b8] cursor-pointer hover:text-[#f8fafc]" data-icon="settings">settings</span>
<span class="material-symbols-outlined text-[#94a3b8] cursor-pointer hover:text-[#f8fafc]" data-icon="account_circle">account_circle</span>
</div>
</div>
</header>
<!-- SideNavBar -->
<aside class="fixed left-0 top-16 h-[calc(100vh-64px)] w-64 bg-[#0b1326] flex flex-col pt-4 z-40">
<div class="px-6 mb-8">
<div class="font-['Space_Grotesk'] text-xs uppercase tracking-[0.2em] text-[#94a3b8]">Market Terminal</div>
<div class="text-[#adc6ff] text-[10px] uppercase tracking-widest mt-1 opacity-60">Precision Intelligence</div>
</div>
<nav class="flex-1">
<ul class="space-y-1">
<li class="px-2">
<a class="flex items-center gap-3 px-4 py-3 bg-[#2d3449] text-[#adc6ff] border-l-2 border-[#adc6ff] font-label text-xs uppercase tracking-widest transition-all duration-200" href="#">
<span class="material-symbols-outlined text-sm" data-icon="dashboard">dashboard</span>
                        Dashboard
                    </a>
</li>
<li class="px-2">
<a class="flex items-center gap-3 px-4 py-3 text-[#94a3b8] hover:bg-[#131b2e] hover:text-[#f8fafc] font-label text-xs uppercase tracking-widest transition-all duration-200" href="#">
<span class="material-symbols-outlined text-sm" data-icon="search_insights">search_insights</span>
                        Market Search
                    </a>
</li>
<li class="px-2">
<a class="flex items-center gap-3 px-4 py-3 text-[#94a3b8] hover:bg-[#131b2e] hover:text-[#f8fafc] font-label text-xs uppercase tracking-widest transition-all duration-200" href="#">
<span class="material-symbols-outlined text-sm" data-icon="calculate">calculate</span>
                        Import Calculator
                    </a>
</li>
<li class="px-2">
<a class="flex items-center gap-3 px-4 py-3 text-[#94a3b8] hover:bg-[#131b2e] hover:text-[#f8fafc] font-label text-xs uppercase tracking-widest transition-all duration-200" href="#">
<span class="material-symbols-outlined text-sm" data-icon="analytics">analytics</span>
                        Saved Reports
                    </a>
</li>
<li class="px-2">
<a class="flex items-center gap-3 px-4 py-3 text-[#94a3b8] hover:bg-[#131b2e] hover:text-[#f8fafc] font-label text-xs uppercase tracking-widest transition-all duration-200" href="#">
<span class="material-symbols-outlined text-sm" data-icon="security">security</span>
                        Intelligence Settings
                    </a>
</li>
</ul>
</nav>
<div class="mt-auto p-4 border-t border-[#424754]/15">
<div class="flex flex-col gap-2">
<a class="flex items-center gap-2 text-[10px] text-[#94a3b8] uppercase tracking-widest hover:text-white" href="#">
<span class="material-symbols-outlined text-xs" data-icon="sensors">sensors</span> System Status: Online
                </a>
<a class="flex items-center gap-2 text-[10px] text-[#94a3b8] uppercase tracking-widest hover:text-white" href="#">
<span class="material-symbols-outlined text-xs" data-icon="help_outline">help_outline</span> Support
                </a>
</div>
</div>
</aside>
<!-- Main Content Area -->
<main class="ml-64 mt-16 p-8 min-h-screen">
<!-- Header Section -->
<div class="flex justify-between items-end mb-10">
<div>
<h1 class="text-3xl font-black text-on-surface tracking-tighter uppercase">Market Comparison Dashboard</h1>
<p class="text-on-surface-variant font-label text-xs tracking-widest mt-1">GERMANY [DE] → SPAIN [ES] ARBITRAGE ANALYSIS</p>
</div>
<div class="flex gap-4">
<div class="text-right">
<div class="text-[10px] text-[#94a3b8] uppercase tracking-widest">Last Updated</div>
<div class="text-sm font-label font-bold text-secondary">LIVE: 14:02:45 UTC</div>
</div>
<button class="bg-surface-container-highest px-4 py-2 text-xs font-bold uppercase tracking-widest sharp-edge border border-outline-variant/20 hover:bg-surface-bright transition-colors">
                    Export Analysis
                </button>
</div>
</div>
<!-- Executive Summary Cards -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
<div class="bg-surface-container-low p-6 border-l-2 border-primary relative overflow-hidden">
<div class="text-[10px] text-on-surface-variant uppercase tracking-widest mb-2 font-label">Market Listings</div>
<div class="flex items-baseline gap-2">
<span class="text-2xl font-black text-white">2,450</span>
<span class="text-xs text-on-surface-variant uppercase tracking-tighter">DE</span>
<span class="text-xs text-on-surface-variant px-2">vs</span>
<span class="text-2xl font-black text-white">1,820</span>
<span class="text-xs text-on-surface-variant uppercase tracking-tighter">ES</span>
</div>
<div class="mt-4 h-1 w-full bg-surface-container">
<div class="h-1 bg-primary w-3/5"></div>
</div>
</div>
<div class="bg-surface-container-low p-6 border-l-2 border-on-surface-variant relative overflow-hidden">
<div class="text-[10px] text-on-surface-variant uppercase tracking-widest mb-2 font-label">Average Price (911 Segment)</div>
<div class="flex items-baseline gap-2">
<span class="text-2xl font-black text-white">92,400€</span>
<span class="text-xs text-on-surface-variant uppercase tracking-tighter">DE</span>
<span class="text-xs text-on-surface-variant px-2">/</span>
<span class="text-2xl font-black text-white">108,100€</span>
<span class="text-xs text-on-surface-variant uppercase tracking-tighter">ES</span>
</div>
</div>
<div class="bg-surface-container-low p-6 border-l-2 border-secondary relative overflow-hidden">
<div class="text-[10px] text-on-surface-variant uppercase tracking-widest mb-2 font-label">Avg. Potential Margin</div>
<div class="flex items-baseline gap-2">
<span class="text-3xl font-black text-secondary">15,700€</span>
<span class="text-xs text-secondary/60 uppercase tracking-widest font-bold">Gross</span>
</div>
<div class="mt-2 text-[10px] text-secondary font-bold tracking-widest">+4.2% FROM LAST WEEK</div>
</div>
<div class="bg-surface-container-low p-6 border-l-2 border-tertiary relative overflow-hidden">
<div class="text-[10px] text-on-surface-variant uppercase tracking-widest mb-2 font-label">Market Confidence</div>
<div class="flex items-baseline gap-2">
<span class="text-3xl font-black text-white">88%</span>
<span class="text-xs text-tertiary uppercase tracking-widest font-bold">Stable</span>
</div>
</div>
</div>
<div class="flex gap-8 items-start">
<!-- Comparison Filter Panel -->
<div class="w-72 flex-shrink-0 bg-surface-container-low p-6 border border-outline-variant/10">
<h3 class="text-xs font-black uppercase tracking-[0.2em] mb-6 border-b border-outline-variant/10 pb-4 flex items-center gap-2">
<span class="material-symbols-outlined text-sm" data-icon="filter_list">filter_list</span> Intelligence Filters
                </h3>
<div class="space-y-6">
<div>
<label class="block text-[10px] uppercase font-label tracking-widest text-[#94a3b8] mb-2">Vehicle Configuration</label>
<select class="w-full bg-surface-container-highest border-none text-xs sharp-edge text-white p-3 font-bold focus:ring-1 focus:ring-primary">
<option>Porsche 911 (All)</option>
<option>BMW M-Series</option>
<option>Audi RS</option>
</select>
</div>
<div class="grid grid-cols-2 gap-2">
<div>
<label class="block text-[10px] uppercase font-label tracking-widest text-[#94a3b8] mb-2">Year Min</label>
<input class="w-full bg-surface-container-highest border-none text-xs sharp-edge text-white p-3 font-bold focus:ring-1 focus:ring-primary" type="text" value="2018"/>
</div>
<div>
<label class="block text-[10px] uppercase font-label tracking-widest text-[#94a3b8] mb-2">Year Max</label>
<input class="w-full bg-surface-container-highest border-none text-xs sharp-edge text-white p-3 font-bold focus:ring-1 focus:ring-primary" type="text" value="2024"/>
</div>
</div>
<div>
<label class="block text-[10px] uppercase font-label tracking-widest text-[#94a3b8] mb-2">Mileage Max (km)</label>
<input class="w-full accent-primary bg-surface-container-highest h-1 appearance-none" type="range"/>
<div class="flex justify-between mt-2 text-[10px] text-[#94a3b8] font-bold">
<span>0</span>
<span>100,000</span>
</div>
</div>
<div>
<label class="block text-[10px] uppercase font-label tracking-widest text-[#94a3b8] mb-2">Power (HP)</label>
<div class="flex items-center gap-2">
<input class="w-full bg-surface-container-highest border-none text-xs sharp-edge text-white p-3 font-bold" placeholder="Min" type="text"/>
<span class="text-[#94a3b8]">-</span>
<input class="w-full bg-surface-container-highest border-none text-xs sharp-edge text-white p-3 font-bold" placeholder="Max" type="text"/>
</div>
</div>
<div class="pt-4 space-y-3">
<label class="flex items-center gap-3 cursor-pointer">
<input checked="" class="rounded-none border-none bg-surface-container-highest text-primary focus:ring-0 w-4 h-4" type="checkbox"/>
<span class="text-[10px] uppercase font-label tracking-widest text-on-surface">Verified Sellers Only</span>
</label>
<label class="flex items-center gap-3 cursor-pointer">
<input class="rounded-none border-none bg-surface-container-highest text-primary focus:ring-0 w-4 h-4" type="checkbox"/>
<span class="text-[10px] uppercase font-label tracking-widest text-on-surface">VAT Deductible</span>
</label>
</div>
<button class="w-full bg-primary py-3 text-on-primary font-black uppercase text-xs tracking-[0.2em] mt-4 sharp-edge hover:brightness-110 active:scale-95 transition-all">
                        Refine Intelligence
                    </button>
</div>
</div>
<!-- Central Opportunities Ranked List -->
<div class="flex-1 space-y-4">
<div class="flex justify-between items-center mb-6">
<h2 class="text-lg font-black uppercase tracking-tighter text-white">Top Import Opportunities</h2>
<div class="flex items-center gap-4 text-xs font-label">
<span class="text-[#94a3b8] uppercase tracking-widest">Sort by:</span>
<select class="bg-transparent border-none text-primary font-bold uppercase tracking-widest p-0 focus:ring-0 cursor-pointer">
<option>Highest Margin</option>
<option>Opportunity Score</option>
<option>Lowest Mileage</option>
</select>
</div>
</div>
<!-- Opportunity Card 1 -->
<div class="bg-surface-container-low p-5 flex items-center gap-6 border border-outline-variant/10 hover:border-primary/40 transition-all group">
<div class="w-32 h-24 bg-surface-container relative overflow-hidden flex-shrink-0">
<img alt="Luxury car" class="w-full h-full object-cover opacity-80 group-hover:scale-110 transition-transform duration-500" data-alt="Side profile of a dark metallic grey luxury sports car parked in a minimalist concrete architectural garage with moody lighting." src="https://lh3.googleusercontent.com/aida-public/AB6AXuBLnauS7MhHkr1osVoouXSzt7YQb0VHUrcXGqcCAlLAHBEGmd5hQWxBla5EsvmcjC6hKftqf2YcPqKMMXSe-npAp3wAIguCMFEumb5_DErMnTHtwz5XM7j5rFyhQWwuee1hyHqEMBivCjPrxdkwErr0l57aCqbT5qkYXCPzgfV-axwmB1K-IFU8lHxvV72W-DV2ZUJpgkExccQ1OLxV61F2V_pSM-MOQ2KdLSkAhSZSPr_t0KVQyRDvaRys3WRlsHNCIHOuUC8FMwE"/>
<div class="absolute top-0 left-0 bg-secondary text-[#003919] text-[8px] font-black px-2 py-0.5 uppercase tracking-tighter">EXACT</div>
</div>
<div class="flex-1">
<div class="flex justify-between items-start mb-2">
<div>
<h4 class="text-md font-black text-white uppercase tracking-tighter">Porsche 911 Carrera S (992)</h4>
<div class="flex gap-4 mt-1">
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">2019</span>
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">45,200 KM</span>
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">450 HP</span>
</div>
</div>
<div class="text-right">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label">Opportunity Score</div>
<div class="text-2xl font-black text-secondary">92<span class="text-xs opacity-50">/100</span></div>
</div>
</div>
<div class="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-outline-variant/10">
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">DE Listing Price</div>
<div class="text-sm font-black text-white">89,500€</div>
</div>
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">ES Break-even</div>
<div class="text-sm font-black text-white/70">98,200€</div>
</div>
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">ES Market Avg</div>
<div class="text-sm font-black text-white/70">105,400€</div>
</div>
<div class="text-right">
<div class="text-[8px] text-secondary uppercase tracking-widest font-black mb-1">Net Margin</div>
<div class="text-lg font-black text-secondary">7,200€</div>
</div>
</div>
</div>
<div class="w-px h-16 bg-outline-variant/20 mx-2"></div>
<div class="w-48 space-y-2">
<div class="flex justify-between items-center">
<span class="text-[8px] text-[#94a3b8] uppercase tracking-widest">CO2 Confidence</span>
<span class="text-[8px] bg-secondary/10 text-secondary border border-secondary/20 px-1 font-bold">ORIGINAL</span>
</div>
<div class="flex justify-between items-center">
<span class="text-[8px] text-[#94a3b8] uppercase tracking-widest">Import Costs</span>
<span class="text-[8px] text-white font-bold">8,700€</span>
</div>
<button class="w-full bg-surface-container-highest border border-primary/20 py-2 text-[10px] font-black uppercase tracking-widest text-primary hover:bg-primary hover:text-on-primary transition-all">
                            View Details
                        </button>
</div>
</div>
<!-- Opportunity Card 2 -->
<div class="bg-surface-container-low p-5 flex items-center gap-6 border border-outline-variant/10 hover:border-primary/40 transition-all group">
<div class="w-32 h-24 bg-surface-container relative overflow-hidden flex-shrink-0">
<img alt="Luxury car" class="w-full h-full object-cover opacity-80 group-hover:scale-110 transition-transform duration-500" data-alt="Modern high-performance luxury sedan in electric blue finish, high-angle view on a sleek black reflective surface with sharp studio highlights." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDcBmaDo1hvto-CP45QD039qtzBN-j-swDQDwCgTmiEd3ctUL3_A3wdVp8wMqVLAs6hADEtftXP3a_UQmd9M5bwaK_GbWOyjWkgi9YTOaKNoT4I1m1v6C2Ztekel458AwQ2IOR4f4-ZQhCRLHaAy6rJybDiBWcxxNMktr1AiQwZkXm8nYgNqDRHYUMMZFLOKpW_ar17JsxP7Ux8ZEA314kLTPF4woun8eH5H3MJeJ5bdDREhDQs2Rpcdn0oLYGuc1mGMWn4SpygIvs"/>
<div class="absolute top-0 left-0 bg-tertiary text-on-tertiary text-[8px] font-black px-2 py-0.5 uppercase tracking-tighter">NEAR</div>
</div>
<div class="flex-1">
<div class="flex justify-between items-start mb-2">
<div>
<h4 class="text-md font-black text-white uppercase tracking-tighter">Audi RS6 Avant Quattro</h4>
<div class="flex gap-4 mt-1">
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">2021</span>
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">28,000 KM</span>
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">600 HP</span>
</div>
</div>
<div class="text-right">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label">Opportunity Score</div>
<div class="text-2xl font-black text-secondary">85<span class="text-xs opacity-50">/100</span></div>
</div>
</div>
<div class="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-outline-variant/10">
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">DE Listing Price</div>
<div class="text-sm font-black text-white">102,000€</div>
</div>
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">ES Break-even</div>
<div class="text-sm font-black text-white/70">114,500€</div>
</div>
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">ES Market Avg</div>
<div class="text-sm font-black text-white/70">121,900€</div>
</div>
<div class="text-right">
<div class="text-[8px] text-secondary uppercase tracking-widest font-black mb-1">Net Margin</div>
<div class="text-lg font-black text-secondary">7,400€</div>
</div>
</div>
</div>
<div class="w-px h-16 bg-outline-variant/20 mx-2"></div>
<div class="w-48 space-y-2">
<div class="flex justify-between items-center">
<span class="text-[8px] text-[#94a3b8] uppercase tracking-widest">CO2 Confidence</span>
<span class="text-[8px] bg-tertiary/10 text-tertiary border border-tertiary/20 px-1 font-bold">INFERRED</span>
</div>
<div class="flex justify-between items-center">
<span class="text-[8px] text-[#94a3b8] uppercase tracking-widest">Import Costs</span>
<span class="text-[8px] text-white font-bold">12,500€</span>
</div>
<button class="w-full bg-surface-container-highest border border-primary/20 py-2 text-[10px] font-black uppercase tracking-widest text-primary hover:bg-primary hover:text-on-primary transition-all">
                            View Details
                        </button>
</div>
</div>
<!-- Opportunity Card 3 -->
<div class="bg-surface-container-low p-5 flex items-center gap-6 border border-outline-variant/10 hover:border-primary/40 transition-all group">
<div class="w-32 h-24 bg-surface-container relative overflow-hidden flex-shrink-0">
<img alt="Luxury car" class="w-full h-full object-cover opacity-80 group-hover:scale-110 transition-transform duration-500" data-alt="Modern yellow sports car in motion on a coastal road at sunrise, high speed blur on the wheels and background sea cliffs." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCIDTWK9LzT9uxOgo4OWD_3pZIu2yJ7nC_qqCBzmfxzIL7jAbF3KQUwJig2NRpYeEXMyOOeA6tDotY9pRFRmJVCpaoAvsmELIchDKWBWJQmb-sfUcQKAFG629Swuiyn0sNNcswCUxlT7Jxvp1ozq0F35FJfe8OgWSmANKMd5g5R7RYh_0fxEwGekOznG4i1RzO8WziyCHambsa2QW8-ePjfk_fuq_vQiPeSjaQgqYgNofjbivEH-dymCGoSP18Y_lCKO4gDLWhrAN8"/>
<div class="absolute top-0 left-0 bg-[#424754] text-white text-[8px] font-black px-2 py-0.5 uppercase tracking-tighter">BROAD</div>
</div>
<div class="flex-1">
<div class="flex justify-between items-start mb-2">
<div>
<h4 class="text-md font-black text-white uppercase tracking-tighter">BMW M5 Competition</h4>
<div class="flex gap-4 mt-1">
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">2022</span>
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">12,500 KM</span>
<span class="text-[10px] text-[#94a3b8] font-label uppercase tracking-widest">625 HP</span>
</div>
</div>
<div class="text-right">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label">Opportunity Score</div>
<div class="text-2xl font-black text-[#94a3b8]">71<span class="text-xs opacity-50">/100</span></div>
</div>
</div>
<div class="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-outline-variant/10">
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">DE Listing Price</div>
<div class="text-sm font-black text-white">94,000€</div>
</div>
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">ES Break-even</div>
<div class="text-sm font-black text-white/70">109,200€</div>
</div>
<div>
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">ES Market Avg</div>
<div class="text-sm font-black text-white/70">114,800€</div>
</div>
<div class="text-right">
<div class="text-[8px] text-secondary uppercase tracking-widest font-black mb-1">Net Margin</div>
<div class="text-lg font-black text-secondary">5,600€</div>
</div>
</div>
</div>
<div class="w-px h-16 bg-outline-variant/20 mx-2"></div>
<div class="w-48 space-y-2">
<div class="flex justify-between items-center">
<span class="text-[8px] text-[#94a3b8] uppercase tracking-widest">CO2 Confidence</span>
<span class="text-[8px] bg-error/10 text-error border border-error/20 px-1 font-bold uppercase tracking-widest">Missing</span>
</div>
<div class="flex justify-between items-center">
<span class="text-[8px] text-[#94a3b8] uppercase tracking-widest">Import Costs</span>
<span class="text-[8px] text-white font-bold">15,200€</span>
</div>
<button class="w-full bg-surface-container-highest border border-primary/20 py-2 text-[10px] font-black uppercase tracking-widest text-primary hover:bg-primary hover:text-on-primary transition-all">
                            View Details
                        </button>
</div>
</div>
</div>
</div>
</main>
<!-- NavigationDrawer (Right-anchored, Hidden by default but structured) -->
<div class="fixed right-0 top-0 h-screen w-[450px] bg-[#131b2e]/80 backdrop-blur-md border-l border-[#424754]/15 shadow-[-20px_0_30px_rgba(6,14,32,0.5)] translate-x-full transition-transform duration-300 z-[60] p-6 flex flex-col" id="detailDrawer">
<div class="flex justify-between items-start mb-8">
<div>
<h2 class="text-[#adc6ff] font-bold text-xl uppercase tracking-tighter">Vehicle Intelligence</h2>
<p class="text-on-surface-variant font-label text-[10px] tracking-widest uppercase">Import Opportunity Detail</p>
</div>
<button class="text-on-surface-variant hover:text-white">
<span class="material-symbols-outlined" data-icon="close">close</span>
</button>
</div>
<div class="flex-1 overflow-y-auto space-y-8 pr-2">
<!-- Cost Breakdown Section -->
<section>
<h3 class="text-xs font-black uppercase tracking-[0.2em] text-white mb-4 border-b border-outline-variant/10 pb-2">Import Cost Breakdown</h3>
<div class="space-y-3">
<div class="flex justify-between text-xs font-label">
<span class="text-[#94a3b8]">Net Acquisition (DE)</span>
<span class="text-white font-bold">89,500€</span>
</div>
<div class="flex justify-between text-xs font-label">
<span class="text-[#94a3b8]">Logistic / Transport</span>
<span class="text-white font-bold">1,200€</span>
</div>
<div class="flex justify-between text-xs font-label">
<span class="text-[#94a3b8]">Registration Tax (IEDMT)</span>
<span class="text-white font-bold">6,850€</span>
</div>
<div class="flex justify-between text-xs font-label border-t border-outline-variant/10 pt-2 mt-2">
<span class="text-white font-black uppercase tracking-widest">Total On-The-Road</span>
<span class="text-white font-black">98,200€</span>
</div>
</div>
</section>
<!-- Technical Analysis -->
<section>
<h3 class="text-xs font-black uppercase tracking-[0.2em] text-white mb-4 border-b border-outline-variant/10 pb-2">Technical Match Data</h3>
<div class="grid grid-cols-2 gap-4">
<div class="bg-surface-container p-3">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">Engine Code</div>
<div class="text-xs font-bold text-white">MA1.01</div>
</div>
<div class="bg-surface-container p-3">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">Chassis Code</div>
<div class="text-xs font-bold text-white">992.1</div>
</div>
<div class="bg-surface-container p-3">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">CO2 (WLTP)</div>
<div class="text-xs font-bold text-secondary">224 g/km</div>
</div>
<div class="bg-surface-container p-3">
<div class="text-[8px] text-[#94a3b8] uppercase tracking-widest font-label mb-1">Drivetrain</div>
<div class="text-xs font-bold text-white">RWD</div>
</div>
</div>
</section>
</div>
<div class="pt-6 border-t border-outline-variant/15 mt-auto">
<button class="w-full bg-primary-container text-on-primary-container py-4 font-black uppercase text-xs tracking-[0.2em] sharp-edge hover:brightness-110 active:scale-95 transition-all">
                Export Full Analysis
            </button>
</div>
</div>
</body></html>