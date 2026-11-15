<template>
  <div class="bg-slate-50 min-h-screen font-sans selection:bg-indigo-200">
    
    <div class="relative overflow-hidden pt-24 pb-32 lg:pt-36">
      <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] opacity-30 pointer-events-none">
        <div class="absolute inset-0 bg-gradient-to-r from-violet-400 to-indigo-500 blur-[100px] rounded-full mix-blend-multiply"></div>
      </div>

      <div class="relative mx-auto max-w-7xl px-6 lg:px-8 flex flex-col lg:flex-row items-center gap-16">
        
        <div class="max-w-2xl lg:w-1/2 lg:max-w-none text-center lg:text-left z-10">
          <div class="inline-flex items-center px-3 py-1 rounded-full bg-indigo-100 text-indigo-700 text-sm font-semibold mb-6 border border-indigo-200">
            <span class="flex w-2 h-2 rounded-full bg-indigo-600 mr-2 animate-pulse"></span>
            DocuMind AI v1.0 is Live
          </div>
          <h1 class="text-5xl font-extrabold tracking-tight text-slate-900 sm:text-6xl lg:text-7xl">
            Give your documents a <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">voice.</span>
          </h1>
          <p class="mt-6 text-lg leading-8 text-slate-600 max-w-xl mx-auto lg:mx-0">
            Stop scrolling through endless PDFs. Upload your research, assignments, or notes, and let our RAG-powered engine find the exact answers you need in seconds.
          </p>
          <div class="mt-10 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
            <router-link to="/register" class="w-full sm:w-auto rounded-xl bg-slate-900 px-8 py-4 text-sm font-bold text-white shadow-lg hover:bg-slate-800 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200">
              Start Chatting Free
            </router-link>
            <router-link to="/login" class="w-full sm:w-auto rounded-xl bg-white px-8 py-4 text-sm font-bold text-slate-700 ring-1 ring-inset ring-slate-200 hover:bg-slate-50 transition-all duration-200">
              Sign In
            </router-link>
          </div>
        </div>

        <div class="w-full lg:w-1/2 z-10 hidden md:block">
          <div class="relative rounded-2xl bg-white/60 backdrop-blur-xl border border-white/40 shadow-2xl p-2 transform rotate-2 hover:rotate-0 transition-transform duration-500">
            <div class="rounded-xl border border-slate-200 bg-slate-50 overflow-hidden shadow-inner">
              <div class="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-2">
                <div class="w-3 h-3 rounded-full bg-red-400"></div>
                <div class="w-3 h-3 rounded-full bg-amber-400"></div>
                <div class="w-3 h-3 rounded-full bg-green-400"></div>
                <div class="ml-4 text-xs font-medium text-slate-400">FYP_Research_Paper.pdf</div>
              </div>
              <div class="p-6 space-y-4 h-64 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9IiNFMkU4RjAiLz48L3N2Zz4=')]">
                <div class="flex justify-end">
                  <div class="bg-indigo-600 text-white text-xs rounded-lg rounded-tr-none px-4 py-2 max-w-[80%] shadow-sm">
                    Summarize the methodology section.
                  </div>
                </div>
                <div class="flex justify-start">
                  <div class="bg-white border border-slate-200 text-slate-700 text-xs rounded-lg rounded-tl-none px-4 py-3 max-w-[80%] shadow-sm leading-relaxed">
                    Based on the document, the methodology uses a mixed-methods approach combining quantitative surveys (n=450) with semi-structured qualitative interviews...
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <div class="py-24 bg-white relative">
      <div class="mx-auto max-w-7xl px-6 lg:px-8">
        <div class="mb-16 max-w-2xl text-center mx-auto">
          <h2 class="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Built for serious research</h2>
          <p class="mt-4 text-slate-600">Everything you need to process complex documents, packaged in a beautifully simple interface.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          <div class="bg-slate-50 rounded-3xl p-8 ring-1 ring-slate-200 hover:shadow-lg transition-shadow duration-300 relative overflow-hidden group">
            <div class="absolute top-0 right-0 w-32 h-32 bg-indigo-100 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
            <div class="w-12 h-12 bg-white rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center mb-6 relative z-10">
              <svg class="w-6 h-6 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
            </div>
            <h3 class="text-lg font-bold text-slate-900 relative z-10">Universal Uploads</h3>
            <p class="mt-2 text-sm text-slate-600 leading-relaxed relative z-10">Drop in PDFs, Word docs, or images. Our backend OCR automatically strips the text and preps it for the AI.</p>
          </div>

          <div class="bg-slate-50 rounded-3xl p-8 ring-1 ring-slate-200 hover:shadow-lg transition-shadow duration-300 relative overflow-hidden group">
            <div class="absolute top-0 right-0 w-32 h-32 bg-violet-100 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
            <div class="w-12 h-12 bg-white rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center mb-6 relative z-10">
              <svg class="w-6 h-6 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <h3 class="text-lg font-bold text-slate-900 relative z-10">Gemini Powered</h3>
            <p class="mt-2 text-sm text-slate-600 leading-relaxed relative z-10">We bypassed basic models. DocuMind uses Google's Gemini-1.5-Flash for lightning-fast, highly accurate reasoning.</p>
          </div>

          <div class="bg-slate-50 rounded-3xl p-8 ring-1 ring-slate-200 hover:shadow-lg transition-shadow duration-300 relative overflow-hidden group">
            <div class="absolute top-0 right-0 w-32 h-32 bg-emerald-100 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
            <div class="w-12 h-12 bg-white rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center mb-6 relative z-10">
              <svg class="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
            </div>
            <h3 class="text-lg font-bold text-slate-900 relative z-10">Isolated Vaults</h3>
            <p class="mt-2 text-sm text-slate-600 leading-relaxed relative z-10">Thanks to JWT Authentication, your files and vector embeddings are cryptographically locked to your account.</p>
          </div>

        </div>
      </div>
    </div>

  </div>
</template>