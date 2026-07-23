<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MaagapAruga — Research & Educational Care Platform</title>
    <link rel="icon" type="image/svg+xml" href="/logo.svg">
    <!-- Tailwind Play CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Google Fonts: Inter for sleek, developer-portfolio feel -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    
    <script>
        tailwind.config = {
            darkMode: 'media',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                    },
                    colors: {
                        brand: {
                            50: '#f0fdfa',
                            100: '#ccfbf1',
                            500: '#14b8a6',
                            600: '#0d9488',
                            700: '#0f766e',
                            800: '#115e59',
                        }
                    }
                }
            }
        }
    </script>

    <style>
        /* Custom grid background effect */
        .grid-bg {
            background-image: radial-gradient(rgba(20, 184, 166, 0.08) 1px, transparent 1px), radial-gradient(rgba(20, 184, 166, 0.05) 1px, transparent 1px);
            background-size: 40px 40px;
            background-position: 0 0, 20px 20px;
        }
        .dark .grid-bg {
            background-image: radial-gradient(rgba(20, 184, 166, 0.05) 1px, transparent 1px), radial-gradient(rgba(20, 184, 166, 0.02) 1px, transparent 1px);
        }
    </style>
</head>
<body class="bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 font-sans transition-colors duration-200 antialiased grid-bg">

    <!-- Top Disclaimer Banner -->
    <div class="bg-amber-50 dark:bg-amber-950/20 border-b border-amber-200/50 dark:border-amber-900/30 px-4 py-3 text-center text-xs text-amber-800 dark:text-amber-300 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto flex items-center justify-center gap-2">
            <svg class="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span><strong>Research &amp; Educational Platform:</strong> Not a medical device and not for clinical use. Illustrative demonstration only using fictitious mock data.</span>
        </div>
    </div>

    <!-- Navigation Header -->
    <header class="border-b border-slate-200/60 dark:border-slate-800/40 backdrop-blur-sm bg-white/70 dark:bg-slate-900/60 transition-colors">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <img src="/logo.svg" alt="MaagapAruga logo" class="w-9 h-9" />
                <div>
                    <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-slate-900 to-slate-700 dark:from-slate-100 dark:to-slate-300 bg-clip-text text-transparent">MaagapAruga</span>
                    <span class="block text-[9px] uppercase tracking-widest text-slate-500 dark:text-slate-400 font-medium">Community Care Demo</span>
                </div>
            </div>
            <nav class="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600 dark:text-slate-300">
                <a href="#capabilities" class="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">Capabilities</a>
                <a href="#architecture" class="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">Architecture</a>
                <a href="#roadmap" class="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">Roadmap</a>
                <a href="https://github.com/marco-montesines/maagaparuga" target="_blank" rel="noopener noreferrer" class="hover:text-brand-600 dark:hover:text-brand-500 transition-colors flex items-center gap-1.5">
                    GitHub
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                </a>
            </nav>
            <div class="flex items-center gap-3">
                <a href="/auth/redirect" class="inline-flex items-center justify-center px-4 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200 transition-colors shadow-sm">
                    Sign in
                </a>
            </div>
        </div>
    </header>

    <!-- Hero Section -->
    <section class="relative overflow-hidden py-16 lg:py-24">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div class="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div class="text-center lg:text-left max-w-2xl mx-auto lg:mx-0">
                <!-- Ethos Tag -->
                <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-brand-50 text-brand-700 dark:bg-brand-950/30 dark:text-brand-300 border border-brand-200/50 dark:border-brand-900/30 mb-6">
                    <span class="w-1.5 h-1.5 rounded-full bg-brand-500 animate-ping"></span>
                    Detect early, assess continuously, refer promptly
                </span>
                
                <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-slate-900 dark:text-white mb-6">
                    Proactive &amp; Compassionate <br>
                    <span class="bg-gradient-to-r from-brand-600 to-teal-400 bg-clip-text text-transparent">Community Care Research</span>
                </h1>
                
                <p class="text-base sm:text-lg text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
                    MaagapAruga is an open-source research and educational demonstration platform. It features polyglot microservices orchestrating care records, real-time vitals ingestion simulators, and automated assessment scoring.
                </p>

                <!-- Actions -->
                <div class="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
                    <a href="https://github.com/marco-montesines/maagaparuga" target="_blank" rel="noopener noreferrer" class="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg border border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900 font-semibold text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors gap-2 shadow-sm text-slate-700 dark:text-slate-200">
                        <svg class="h-5 w-5 text-slate-700 dark:text-slate-300" fill="currentColor" viewBox="0 0 24 24">
                            <path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clip-rule="evenodd" />
                        </svg>
                        View on GitHub
                    </a>
                    <a href="/auth/redirect" class="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg bg-gradient-to-r from-brand-600 to-teal-500 hover:from-brand-700 hover:to-teal-600 text-white font-semibold text-sm transition-all shadow-md shadow-brand-600/10">
                        Sign in to Dashboard
                    </a>
                </div>

                <!-- Lineage Sub-strip -->
                <div class="mt-12 flex flex-col items-center lg:items-start justify-center gap-2">
                    <span class="text-[11px] uppercase tracking-wider text-slate-400 dark:text-slate-500 font-semibold">Architectural Lineage</span>
                    <div class="flex items-center gap-3 text-xs font-medium text-slate-500 dark:text-slate-400">
                        <span>TMIS (2007)</span>
                        <span class="text-slate-300 dark:text-slate-800">•</span>
                        <span>BTMS (2024)</span>
                        <span class="text-slate-300 dark:text-slate-800">•</span>
                        <span>SEDS</span>
                    </div>
                </div>
            </div>
                <!-- Right: hero graphic -->
                <div class="relative flex justify-center lg:justify-end mt-6 lg:mt-0">
                    <img src="/hero.svg" alt="" class="w-full max-w-xs sm:max-w-sm lg:max-w-lg" />
                    <div class="absolute inset-0 -z-10 bg-brand-500/10 rounded-full blur-3xl pointer-events-none"></div>
                </div>
            </div>
        </div>
    </section>

    <!-- Capabilities Grid Section -->
    <section id="capabilities" class="py-20 bg-white/40 dark:bg-slate-900/30 border-y border-slate-200/50 dark:border-slate-800/30">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center max-w-2xl mx-auto mb-16">
                <h2 class="text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-4xl">Platform Capabilities</h2>
                <p class="mt-4 text-slate-600 dark:text-slate-400 text-sm sm:text-base">
                    An examination of the functional layers demonstrating end-to-end community care telemetry and coordination flow.
                </p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                <!-- Care Records -->
                <div class="p-6 rounded-xl border border-slate-200/60 dark:border-slate-800/50 bg-white dark:bg-slate-900/60 shadow-sm hover:shadow-md transition-shadow">
                    <div class="w-10 h-10 rounded-lg bg-teal-50 dark:bg-teal-950/30 flex items-center justify-center text-teal-600 dark:text-teal-400 mb-4">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    </div>
                    <h3 class="font-bold text-slate-900 dark:text-white mb-2">Telemedicine Care Records</h3>
                    <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        Manages unstructured case logs and health profiles. Provides lookup pathways for patient telemetry references using mock identities.
                    </p>
                </div>

                <!-- IoMT Ingest -->
                <div class="p-6 rounded-xl border border-slate-200/60 dark:border-slate-800/50 bg-white dark:bg-slate-900/60 shadow-sm hover:shadow-md transition-shadow">
                    <div class="w-10 h-10 rounded-lg bg-teal-50 dark:bg-teal-950/30 flex items-center justify-center text-teal-600 dark:text-teal-400 mb-4">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    </div>
                    <h3 class="font-bold text-slate-900 dark:text-white mb-2">Vitals &amp; IoMT Ingest</h3>
                    <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        A biotelemetry receiver simulator demonstrating ingestion of mock vital signs (heart rate, SpO2, temperature) from simulated remote home sensors.
                    </p>
                </div>

                <!-- Assessment Scoring -->
                <div class="p-6 rounded-xl border border-slate-200/60 dark:border-slate-800/50 bg-white dark:bg-slate-900/60 shadow-sm hover:shadow-md transition-shadow">
                    <div class="w-10 h-10 rounded-lg bg-teal-50 dark:bg-teal-950/30 flex items-center justify-center text-teal-600 dark:text-teal-400 mb-4">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
                    </div>
                    <h3 class="font-bold text-slate-900 dark:text-white mb-2">Assessment Scoring Engine</h3>
                    <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        Demonstrates calculations for early-warning indicators using NEWS2 protocols, psychological wellness metrics via DASS-21, and fuzzy risk logic.
                    </p>
                </div>

                <!-- Media & Transcription -->
                <div class="p-6 rounded-xl border border-slate-200/60 dark:border-slate-800/50 bg-white dark:bg-slate-900/60 shadow-sm hover:shadow-md transition-shadow">
                    <div class="w-10 h-10 rounded-lg bg-teal-50 dark:bg-teal-950/30 flex items-center justify-center text-teal-600 dark:text-teal-400 mb-4">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
                    </div>
                    <h3 class="font-bold text-slate-900 dark:text-white mb-2">Media &amp; Transcription</h3>
                    <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        Background pipeline demonstrating audio recording intake, voice parsing queues, and transcript compilation of case notes.
                    </p>
                </div>

                <!-- Identity & Auth -->
                <div class="p-6 rounded-xl border border-slate-200/60 dark:border-slate-800/50 bg-white dark:bg-slate-900/60 shadow-sm hover:shadow-md transition-shadow">
                    <div class="w-10 h-10 rounded-lg bg-teal-50 dark:bg-teal-950/30 flex items-center justify-center text-teal-600 dark:text-teal-400 mb-4">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                    </div>
                    <h3 class="font-bold text-slate-900 dark:text-white mb-2">Identity &amp; Authorization</h3>
                    <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        Security-by-design demonstration leveraging OIDC SSO protocols coupled with granular relationship-based authorization models.
                    </p>
                </div>

                <!-- Observability -->
                <div class="p-6 rounded-xl border border-slate-200/60 dark:border-slate-800/50 bg-white dark:bg-slate-900/60 shadow-sm hover:shadow-md transition-shadow">
                    <div class="w-10 h-10 rounded-lg bg-teal-50 dark:bg-teal-950/30 flex items-center justify-center text-teal-600 dark:text-teal-400 mb-4">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                    </div>
                    <h3 class="font-bold text-slate-900 dark:text-white mb-2">Observability &amp; Backups</h3>
                    <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                        Centralized metrics collection, request trace correlation across microservices, and scheduled mock backup routines.
                    </p>
                </div>
            </div>
        </div>
    </section>

    <!-- Tech/Architecture Strip Section -->
    <section id="architecture" class="py-20 relative overflow-hidden">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center max-w-2xl mx-auto mb-16">
                <h2 class="text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-4xl">Technical Architecture</h2>
                <p class="mt-4 text-slate-600 dark:text-slate-400 text-sm sm:text-base">
                    Designed as a polyglot microservice layout mapping specific workloads to optimal persistence models.
                </p>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <!-- Kubernetes -->
                <div class="p-5 rounded-lg border border-slate-200/50 dark:border-slate-800/40 bg-white/50 dark:bg-slate-900/40 backdrop-blur-sm">
                    <span class="text-xs font-semibold text-brand-600 dark:text-brand-400 uppercase tracking-widest block mb-1">Infrastructure</span>
                    <h4 class="font-bold text-slate-900 dark:text-white text-base mb-2">Kubernetes</h4>
                    <p class="text-xs text-slate-600 dark:text-slate-400">
                        Container orchestration configuration templates showcasing service discoverability, persistent volume binds, and internal cluster routing.
                    </p>
                </div>

                <!-- Polyglot Services -->
                <div class="p-5 rounded-lg border border-slate-200/50 dark:border-slate-800/40 bg-white/50 dark:bg-slate-900/40 backdrop-blur-sm">
                    <span class="text-xs font-semibold text-brand-600 dark:text-brand-400 uppercase tracking-widest block mb-1">Execution</span>
                    <h4 class="font-bold text-slate-900 dark:text-white text-base mb-2">Polyglot Microservices</h4>
                    <p class="text-xs text-slate-600 dark:text-slate-400">
                        Demonstration code written in Go (ingest pipelines), Python (transcription tasks), and PHP running on FrankenPHP (web portal &amp; orchestration).
                    </p>
                </div>

                <!-- API Gateway -->
                <div class="p-5 rounded-lg border border-slate-200/50 dark:border-slate-800/40 bg-white/50 dark:bg-slate-900/40 backdrop-blur-sm">
                    <span class="text-xs font-semibold text-brand-600 dark:text-brand-400 uppercase tracking-widest block mb-1">Routing</span>
                    <h4 class="font-bold text-slate-900 dark:text-white text-base mb-2">API Gateway</h4>
                    <p class="text-xs text-slate-600 dark:text-slate-400">
                        Acts as the single point of entry, routing requests, handling edge termination, and mapping upstream headers.
                    </p>
                </div>

                <!-- Right Store -->
                <div class="p-5 rounded-lg border border-slate-200/50 dark:border-slate-800/40 bg-white/50 dark:bg-slate-900/40 backdrop-blur-sm">
                    <span class="text-xs font-semibold text-brand-600 dark:text-brand-400 uppercase tracking-widest block mb-1">Persistence</span>
                    <h4 class="font-bold text-slate-900 dark:text-white text-base mb-2">Right-Store-per-Workload</h4>
                    <p class="text-xs text-slate-600 dark:text-slate-400">
                        Tailored storage layer leveraging relational tables for schema integrity, time-series for vitals logs, and document stores for records.
                    </p>
                </div>
            </div>
        </div>
    </section>

    <!-- Roadmap Teaser Section -->
    <section id="roadmap" class="py-20 bg-slate-100/50 dark:bg-slate-900/20 border-t border-slate-200/50 dark:border-slate-800/30">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="max-w-3xl mx-auto">
                <div class="text-center mb-12">
                    <h2 class="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Roadmap</h2>
                    <p class="mt-2 text-slate-600 dark:text-slate-400 text-sm">
                        Where the platform is headed beyond its initial build — research and feature directions, explored on fictitious data only.
                    </p>
                </div>

                <!-- Roadmap steps -->
                <div class="space-y-8 relative before:absolute before:inset-0 before:left-4 sm:before:left-1/2 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800 pointer-events-none">
                    <!-- Step 1 -->
                    <div class="relative flex flex-col sm:flex-row items-start sm:items-center">
                        <div class="absolute left-4 sm:left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-brand-500 border-4 border-slate-100 dark:border-slate-950 z-10"></div>
                        <div class="pl-12 sm:pl-0 sm:w-1/2 sm:pr-8 sm:text-right">
                            <span class="text-xs font-bold text-brand-600 dark:text-brand-400 uppercase">Near-term</span>
                            <h4 class="font-bold text-slate-950 dark:text-white text-sm mt-1">Richer IoMT Device Fleet</h4>
                            <p class="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-sm sm:ml-auto">
                                A fuller mock device fleet with distinct personalities and an MQTT ingest path, driving alert storylines end to end.
                            </p>
                        </div>
                        <div class="hidden sm:block sm:w-1/2"></div>
                    </div>

                    <!-- Step 2 -->
                    <div class="relative flex flex-col sm:flex-row items-start sm:items-center">
                        <div class="absolute left-4 sm:left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-brand-500 border-4 border-slate-100 dark:border-slate-950 z-10"></div>
                        <div class="hidden sm:block sm:w-1/2"></div>
                        <div class="pl-12 sm:pl-8 sm:w-1/2">
                            <span class="text-xs font-bold text-brand-600 dark:text-brand-400 uppercase">Next</span>
                            <h4 class="font-bold text-slate-950 dark:text-white text-sm mt-1">Full Observability</h4>
                            <p class="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-sm">
                                OpenTelemetry tracing across the polyglot services, with dashboards and actionable alerting.
                            </p>
                        </div>
                    </div>

                    <!-- Step 3 -->
                    <div class="relative flex flex-col sm:flex-row items-start sm:items-center">
                        <div class="absolute left-4 sm:left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-slate-300 dark:bg-slate-700 border-4 border-slate-100 dark:border-slate-950 z-10"></div>
                        <div class="pl-12 sm:pl-0 sm:w-1/2 sm:pr-8 sm:text-right">
                            <span class="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase">Research</span>
                            <h4 class="font-bold text-slate-950 dark:text-white text-sm mt-1">Privacy-Preserving ML</h4>
                            <p class="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-sm sm:ml-auto">
                                On synthetic data only — differential privacy and federated learning as a demonstration of technique, never real records.
                            </p>
                        </div>
                        <div class="hidden sm:block sm:w-1/2"></div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer Section -->
    <footer class="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 py-12 transition-colors">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
                <div>
                    <div class="flex items-center gap-2 mb-3">
                        <img src="/logo.svg" alt="MaagapAruga logo" class="w-6 h-6" />
                        <span class="font-bold text-slate-900 dark:text-white text-sm">MaagapAruga</span>
                    </div>
                    <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-md">
                        An educational platform demonstrating microservice integration, telemetry ingestion, and assessment flows. Inspired by prior architectures TMIS (2007), BTMS (2024), and SEDS.
                    </p>
                </div>
                <div class="md:text-right flex flex-col md:items-end gap-3">
                    <div class="flex items-center gap-4 text-xs font-medium text-slate-600 dark:text-slate-400">
                        <a href="https://github.com/marco-montesines/maagaparuga" target="_blank" rel="noopener noreferrer" class="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">GitHub Repository</a>
                        <span class="text-slate-300 dark:text-slate-800">|</span>
                        <a href="https://github.com/marco-montesines/maagaparuga/blob/master/ROADMAP.md" target="_blank" rel="noopener noreferrer" class="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">Roadmap</a>
                        <span class="text-slate-300 dark:text-slate-800">|</span>
                        <span>Apache-2.0 License</span>
                    </div>
                    <span class="text-[10px] text-slate-400 dark:text-slate-500">© 2026 MaagapAruga Open-Source Project.</span>
                </div>
            </div>

            <!-- Crucial Legal Disclaimer -->
            <div class="mt-8 pt-6 border-t border-slate-100 dark:border-slate-900/60 text-center">
                <p class="text-[10px] sm:text-xs text-slate-400 dark:text-slate-500 leading-relaxed max-w-3xl mx-auto">
                    <strong>Disclaimer:</strong> MaagapAruga is an open-source educational and research demonstration framework. It is <strong>NOT</strong> a medical device, is not intended for clinical use, and does not provide medical advice or treatment assessments. All data generated and displayed by the system is fictitious and used for illustrative purposes only.
                </p>
            </div>
        </div>
    </footer>

</body>
</html>
