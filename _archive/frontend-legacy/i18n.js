/* ============================================
   QUANT API PLATFORM — Internationalization
   Complete Chinese (zh-CN) + English (en) system
   ============================================ */

const I18N = {
  en: {
    // -- App Shell --
    brand_name: 'QUANT_CORE',
    brand_status_active: 'SYSTEM ACTIVE',
    brand_status_offline: 'SYSTEM OFFLINE',
    studio_brand: 'STUDIO_Q1',
    search_placeholder: 'SEARCH INSTRUMENTS...',

    // -- Sidebar Navigation --
    nav_dashboard: 'DASHBOARD',
    nav_instruments: 'INSTRUMENTS',
    nav_research: 'RESEARCH',
    nav_backtest: 'BACKTEST',
    nav_execution: 'EXECUTION',
    nav_dq: 'DATA QUALITY',
    nav_settings: 'SETTINGS',
    nav_new_backtest: 'NEW_BACKTEST',
    nav_api_docs: 'API DOCS',
    nav_github: 'GITHUB',

    // -- Topbar Tabs --
    tab_dashboard: 'DASHBOARD',
    tab_instruments: 'INSTRUMENTS',
    tab_research: 'RESEARCH',
    tab_backtests: 'BACKTESTS',
    tab_orders: 'ORDERS',

    // -- Dashboard Page --
    dash_title: 'Executive Dashboard',
    dash_title_accent: '- Live',
    dash_subtitle_prefix: 'PLATFORM STATUS:',
    dash_subtitle_status: 'OPERATIONAL',
    dash_subtitle_market: '// MARKET: US EQUITIES',
    dash_export_report: 'EXPORT REPORT',
    dash_sync_data: 'SYNC DATA',
    dash_platform_health: 'PLATFORM HEALTH',
    dash_test_pass_label: 'Test pass rate across all modules',
    dash_system_modules: 'SYSTEM MODULES',
    dash_realtime_logs: 'REAL-TIME LOGS',
    dash_view_api_docs: 'VIEW API DOCS',
    dash_data_coverage: 'Data Coverage',
    dash_data_coverage_sub: 'PRICE BARS ACROSS 4 INSTRUMENTS',
    dash_total_bars: 'TOTAL BARS',
    dash_total_instruments: 'INSTRUMENTS',
    dash_system_health: 'SYSTEM HEALTH',
    dash_active_instruments: 'ACTIVE INSTRUMENTS',
    dash_recent_backtests: 'RECENT BACKTESTS',
    dash_run_new: '+ RUN NEW',
    dash_data_quality: 'DATA QUALITY',
    dash_execution_pipeline: 'EXECUTION PIPELINE',
    dash_no_backtests: 'No backtests yet. Click "+ RUN NEW" to start.',

    // -- Module Names --
    module_data_layer: 'Data Layer',
    module_research: 'Research',
    module_backtest: 'Backtest',
    module_execution: 'Execution',
    module_dq: 'DQ Engine',

    // -- Status Labels --
    status_active: 'ACTIVE',
    status_controlled: 'CONTROLLED',
    status_idle: 'IDLE',
    status_queued: 'QUEUED',
    status_alert: 'ALERT',
    status_healthy: 'HEALTHY',
    status_locked: 'LOCKED',
    status_pending: 'PENDING',
    status_approved: 'APPROVED',
    status_rejected: 'REJECTED',
    status_submitted: 'SUBMITTED',
    status_filled: 'FILLED',
    status_cancelled: 'CANCELLED',
    status_expired: 'EXPIRED',
    status_pass: 'PASS',
    status_fail: 'FAIL',
    status_configured: 'Configured',
    status_not_configured: 'Not Configured',

    // -- Table Headers --
    th_ticker: 'TICKER',
    th_issuer_name: 'ISSUER NAME',
    th_status: 'STATUS',
    th_price_bars: 'PRICE BARS',
    th_corp_actions: 'CORP ACTIONS',
    th_filings: 'FILINGS',
    th_last_price: 'LAST PRICE',
    th_asset_type: 'ASSET TYPE',
    th_exchange: 'EXCHANGE',
    th_currency: 'CURRENCY',
    th_identifiers: 'IDENTIFIERS',
    th_strategy: 'STRATEGY',
    th_period: 'PERIOD',
    th_return: 'RETURN',
    th_sharpe: 'SHARPE',
    th_max_dd: 'MAX DD',
    th_trades: 'TRADES',
    th_created: 'CREATED',
    th_instrument: 'INSTRUMENT',
    th_side: 'SIDE',
    th_quantity: 'QUANTITY',
    th_order_type: 'ORDER TYPE',
    th_broker: 'BROKER',
    th_intent_id: 'INTENT ID',
    th_draft_id: 'DRAFT ID',
    th_rule_code: 'RULE CODE',
    th_severity: 'SEVERITY',
    th_table_name: 'TABLE',
    th_details: 'DETAILS',
    th_date: 'DATE',
    th_price: 'PRICE',
    th_cost: 'COST',
    th_notional: 'NOTIONAL',

    // -- Pipeline Stages --
    pipeline_signal: 'Signal',
    pipeline_intent: 'Intent',
    pipeline_draft: 'Draft',
    pipeline_approved: 'Approved',
    pipeline_submit: 'Submit',
    pipeline_locked_note: 'Live submission disabled by policy (FEATURE_T212_LIVE_SUBMIT=false)',

    // -- Pipeline Legend --
    legend_approved: 'Approved',
    legend_pending: 'Pending',
    legend_rejected: 'Rejected',

    // -- Instruments Page --
    instruments_title: 'Instruments & Universe',
    instruments_subtitle: 'Security master with identifier history and market data coverage',
    instruments_detail: 'Instrument Detail',
    instruments_identifiers: 'Identifiers',
    instruments_ticker_history: 'Ticker History',
    instruments_loading: 'Loading instruments...',

    // -- Research Page --
    research_title: 'Research Workbench',
    research_subtitle: 'PIT-safe quantitative analysis with explicit time boundaries',
    research_quick_analysis: 'Quick Analysis',
    research_select_instrument: 'Select Instrument',
    research_asof_date: 'As-of Date',
    research_load_summary: 'Summary',
    research_load_performance: 'Performance',
    research_load_valuation: 'Valuation',
    research_load_drawdown: 'Drawdown',
    research_event_study: 'Event Study',
    research_event_study_desc: 'Post-earnings return analysis (1/3/5/10 day windows)',
    research_run_study: 'RUN STUDY',
    research_screeners: 'Screeners',
    research_screener_liquidity: 'Liquidity Screen',
    research_screener_returns: 'Returns Screen',
    research_screener_fundamentals: 'Fundamentals Screen',
    research_screener_rank: 'Composite Rank',
    research_results: 'Results',
    research_no_results: 'Run an analysis to see results here.',
    research_pit_notice: 'All queries respect PIT boundaries. No future data leakage.',

    // -- Backtest Page --
    backtest_title: 'Backtest Engine',
    backtest_subtitle: 'Run, persist, and analyze strategy backtests',
    backtest_new: 'New Backtest',
    backtest_config: 'Configuration',
    backtest_strategy: 'Strategy',
    backtest_tickers: 'Tickers (comma-separated)',
    backtest_start_date: 'Start Date',
    backtest_end_date: 'End Date',
    backtest_slippage: 'Slippage (bps)',
    backtest_max_positions: 'Max Positions',
    backtest_rebalance: 'Rebalance Frequency',
    backtest_run: 'RUN BACKTEST',
    backtest_cancel: 'CANCEL',
    backtest_running: 'Running backtest...',
    backtest_past_runs: 'Past Runs',
    backtest_no_runs: 'No backtest runs yet.',
    backtest_detail: 'Backtest Detail',
    backtest_metrics: 'Performance Metrics',
    backtest_trades: 'Trade Log',
    backtest_nav_series: 'NAV Series',
    backtest_total_return: 'Total Return',
    backtest_ann_return: 'Ann. Return',
    backtest_volatility: 'Volatility',
    backtest_sharpe_ratio: 'Sharpe Ratio',
    backtest_max_drawdown: 'Max Drawdown',
    backtest_total_trades: 'Total Trades',
    backtest_turnover: 'Turnover',
    backtest_total_costs: 'Total Costs',
    backtest_final_nav: 'Final NAV',
    backtest_initial_capital: 'Initial Capital',
    rebalance_monthly: 'Monthly',
    rebalance_weekly: 'Weekly',
    rebalance_daily: 'Daily',
    strategy_momentum: 'Momentum',
    strategy_equal_weight: 'Equal Weight',

    // -- Execution Page --
    execution_title: 'Execution & Orders',
    execution_subtitle: 'Controlled order pipeline with mandatory approval gates',
    execution_intents: 'Order Intents',
    execution_drafts: 'Order Drafts',
    execution_create_intent: 'Create Intent',
    execution_strategy_name: 'Strategy Name',
    execution_instrument: 'Instrument',
    execution_side: 'Side',
    execution_target_qty: 'Target Quantity',
    execution_reason: 'Reason',
    execution_create: 'CREATE INTENT',
    execution_policy_notice: 'Live submission disabled by policy',
    execution_side_buy: 'BUY',
    execution_side_sell: 'SELL',
    execution_no_intents: 'No order intents. Create one to start.',
    execution_no_drafts: 'No order drafts.',

    // -- DQ Page --
    dq_title: 'Data Quality Engine',
    dq_subtitle: '11 automated rules with persistent issue tracking',
    dq_rules: 'Quality Rules',
    dq_issues: 'Data Issues',
    dq_source_runs: 'Source Runs',
    dq_no_issues: 'No data quality issues found.',
    dq_all_clear: 'ALL CLEAR',
    dq_rule_names: {
      'DQ-1': 'OHLC Logic',
      'DQ-2': 'Non-Negative',
      'DQ-3': 'Duplicate PK',
      'DQ-4': 'Trade Days',
      'DQ-5': 'Corp Actions',
      'DQ-6': 'PIT Check',
      'DQ-7': 'Cross-Source',
      'DQ-8': 'Stale Prices',
      'DQ-9': 'Ticker Overlap',
      'DQ-10': 'Orphan IDs',
      'DQ-11': 'Raw/Adj Mix',
    },

    // -- Settings Page --
    settings_title: 'Configuration & Policies',
    settings_subtitle: 'API keys, feature flags, and execution policies',
    settings_api_keys: 'API Keys',
    settings_feature_flags: 'Feature Flags',
    settings_execution_policy: 'Execution Policy',
    settings_data_sources: 'Data Sources',
    settings_key_names: {
      sec: 'SEC EDGAR',
      openfigi: 'OpenFIGI',
      massive: 'Massive / Polygon',
      fmp: 'Financial Modeling Prep',
      t212: 'Trading 212',
      bea: 'BEA',
      bls: 'BLS',
      treasury: 'US Treasury',
    },

    // -- Log Events --
    log_system_boot: 'SYSTEM_BOOT',
    log_health_check: 'HEALTH_CHECK',
    log_data_loaded: 'DATA_LOADED',
    log_sync_complete: 'SYNC_COMPLETE',
    log_sync_error: 'SYNC_ERROR',
    log_nav: 'NAV',
    log_backtest_start: 'BACKTEST_START',
    log_backtest_done: 'BACKTEST_DONE',
    log_backtest_error: 'BACKTEST_ERROR',
    log_export: 'EXPORT',
    log_dashboard_init: 'Dashboard initialized',
    log_instruments_loaded: 'instruments loaded',
    log_all_refreshed: 'All data refreshed',
    log_page_loaded: 'page loaded',

    // -- Common --
    loading: 'Loading...',
    error_title: 'Error Loading Page',
    retry: 'RETRY',
    cancel: 'CANCEL',
    confirm: 'CONFIRM',
    close: 'CLOSE',
    save: 'SAVE',
    delete: 'DELETE',
    edit: 'EDIT',
    view: 'VIEW',
    refresh: 'REFRESH',
    no_data: 'No data available',
    latency: 'LATENCY',
    version: 'Version',
  },

  'zh-CN': {
    // -- App Shell --
    brand_name: 'QUANT_CORE',
    brand_status_active: '\u7CFB\u7EDF\u8FD0\u884C\u4E2D',
    brand_status_offline: '\u7CFB\u7EDF\u79BB\u7EBF',
    studio_brand: 'STUDIO_Q1',
    search_placeholder: '\u641C\u7D22\u8BC1\u5238...',

    // -- Sidebar Navigation --
    nav_dashboard: '\u4EEA\u8868\u76D8',
    nav_instruments: '\u8BC1\u5238\u7BA1\u7406',
    nav_research: '\u7814\u7A76\u5206\u6790',
    nav_backtest: '\u56DE\u6D4B\u5F15\u64CE',
    nav_execution: '\u6267\u884C\u7BA1\u7406',
    nav_dq: '\u6570\u636E\u8D28\u91CF',
    nav_settings: '\u7CFB\u7EDF\u8BBE\u7F6E',
    nav_new_backtest: '\u65B0\u5EFA\u56DE\u6D4B',
    nav_api_docs: 'API \u6587\u6863',
    nav_github: 'GITHUB',

    // -- Topbar Tabs --
    tab_dashboard: '\u4EEA\u8868\u76D8',
    tab_instruments: '\u8BC1\u5238',
    tab_research: '\u7814\u7A76',
    tab_backtests: '\u56DE\u6D4B',
    tab_orders: '\u8BA2\u5355',

    // -- Dashboard Page --
    dash_title: '\u6267\u884C\u603B\u89C8',
    dash_title_accent: '- \u5B9E\u65F6',
    dash_subtitle_prefix: '\u5E73\u53F0\u72B6\u6001\uFF1A',
    dash_subtitle_status: '\u8FD0\u884C\u6B63\u5E38',
    dash_subtitle_market: '// \u5E02\u573A\uFF1A\u7F8E\u80A1',
    dash_export_report: '\u5BFC\u51FA\u62A5\u544A',
    dash_sync_data: '\u540C\u6B65\u6570\u636E',
    dash_platform_health: '\u5E73\u53F0\u5065\u5EB7',
    dash_test_pass_label: '\u6240\u6709\u6A21\u5757\u6D4B\u8BD5\u901A\u8FC7\u7387',
    dash_system_modules: '\u7CFB\u7EDF\u6A21\u5757',
    dash_realtime_logs: '\u5B9E\u65F6\u65E5\u5FD7',
    dash_view_api_docs: '\u67E5\u770B API \u6587\u6863',
    dash_data_coverage: '\u6570\u636E\u8986\u76D6',
    dash_data_coverage_sub: '4 \u53EA\u8BC1\u5238\u7684\u4EF7\u683C\u6570\u636E',
    dash_total_bars: '\u603B K \u7EBF\u6570',
    dash_total_instruments: '\u8BC1\u5238\u6570',
    dash_system_health: '\u7CFB\u7EDF\u5065\u5EB7',
    dash_active_instruments: '\u6D3B\u8DC3\u8BC1\u5238',
    dash_recent_backtests: '\u6700\u8FD1\u56DE\u6D4B',
    dash_run_new: '+ \u65B0\u5EFA',
    dash_data_quality: '\u6570\u636E\u8D28\u91CF',
    dash_execution_pipeline: '\u6267\u884C\u7BA1\u9053',
    dash_no_backtests: '\u6682\u65E0\u56DE\u6D4B\u8BB0\u5F55\u3002\u70B9\u51FB\u201C+ \u65B0\u5EFA\u201D\u5F00\u59CB\u3002',

    // -- Module Names --
    module_data_layer: '\u6570\u636E\u5C42',
    module_research: '\u7814\u7A76\u5C42',
    module_backtest: '\u56DE\u6D4B\u5C42',
    module_execution: '\u6267\u884C\u5C42',
    module_dq: '\u6570\u636E\u8D28\u91CF',

    // -- Status Labels --
    status_active: '\u8FD0\u884C\u4E2D',
    status_controlled: '\u53D7\u63A7',
    status_idle: '\u7A7A\u95F2',
    status_queued: '\u6392\u961F\u4E2D',
    status_alert: '\u544A\u8B66',
    status_healthy: '\u5065\u5EB7',
    status_locked: '\u5DF2\u9501\u5B9A',
    status_pending: '\u5F85\u5904\u7406',
    status_approved: '\u5DF2\u6279\u51C6',
    status_rejected: '\u5DF2\u62D2\u7EDD',
    status_submitted: '\u5DF2\u63D0\u4EA4',
    status_filled: '\u5DF2\u6210\u4EA4',
    status_cancelled: '\u5DF2\u53D6\u6D88',
    status_expired: '\u5DF2\u8FC7\u671F',
    status_pass: '\u901A\u8FC7',
    status_fail: '\u5931\u8D25',
    status_configured: '\u5DF2\u914D\u7F6E',
    status_not_configured: '\u672A\u914D\u7F6E',

    // -- Table Headers --
    th_ticker: '\u4EE3\u7801',
    th_issuer_name: '\u53D1\u884C\u4EBA\u540D\u79F0',
    th_status: '\u72B6\u6001',
    th_price_bars: '\u4EF7\u683C\u6570\u636E',
    th_corp_actions: '\u516C\u53F8\u884C\u4E3A',
    th_filings: '\u62AB\u9732\u6587\u4EF6',
    th_last_price: '\u6700\u65B0\u4EF7',
    th_asset_type: '\u8D44\u4EA7\u7C7B\u578B',
    th_exchange: '\u4EA4\u6613\u6240',
    th_currency: '\u5E01\u79CD',
    th_identifiers: '\u6807\u8BC6\u7B26',
    th_strategy: '\u7B56\u7565',
    th_period: '\u671F\u95F4',
    th_return: '\u6536\u76CA\u7387',
    th_sharpe: '\u590F\u666E\u6BD4\u7387',
    th_max_dd: '\u6700\u5927\u56DE\u64A4',
    th_trades: '\u4EA4\u6613\u6570',
    th_created: '\u521B\u5EFA\u65F6\u95F4',
    th_instrument: '\u8BC1\u5238',
    th_side: '\u65B9\u5411',
    th_quantity: '\u6570\u91CF',
    th_order_type: '\u8BA2\u5355\u7C7B\u578B',
    th_broker: '\u7ECF\u7EAA\u5546',
    th_intent_id: '\u610F\u56FE ID',
    th_draft_id: '\u8349\u7A3F ID',
    th_rule_code: '\u89C4\u5219\u7F16\u7801',
    th_severity: '\u4E25\u91CD\u7A0B\u5EA6',
    th_table_name: '\u6570\u636E\u8868',
    th_details: '\u8BE6\u60C5',
    th_date: '\u65E5\u671F',
    th_price: '\u4EF7\u683C',
    th_cost: '\u6210\u672C',
    th_notional: '\u540D\u4E49\u91D1\u989D',

    // -- Pipeline Stages --
    pipeline_signal: '\u4FE1\u53F7',
    pipeline_intent: '\u610F\u56FE',
    pipeline_draft: '\u8349\u7A3F',
    pipeline_approved: '\u5DF2\u6279\u51C6',
    pipeline_submit: '\u63D0\u4EA4',
    pipeline_locked_note: '\u5B9E\u76D8\u63D0\u4EA4\u5DF2\u7981\u7528 (FEATURE_T212_LIVE_SUBMIT=false)',

    // -- Pipeline Legend --
    legend_approved: '\u5DF2\u6279\u51C6',
    legend_pending: '\u5F85\u5904\u7406',
    legend_rejected: '\u5DF2\u62D2\u7EDD',

    // -- Instruments Page --
    instruments_title: '\u8BC1\u5238\u4E0E\u6295\u8D44\u7EC4\u5408',
    instruments_subtitle: '\u5305\u542B\u6807\u8BC6\u7B26\u5386\u53F2\u548C\u5E02\u573A\u6570\u636E\u8986\u76D6\u7684\u8BC1\u5238\u4E3B\u6570\u636E',
    instruments_detail: '\u8BC1\u5238\u8BE6\u60C5',
    instruments_identifiers: '\u6807\u8BC6\u7B26',
    instruments_ticker_history: '\u4EE3\u7801\u5386\u53F2',
    instruments_loading: '\u6B63\u5728\u52A0\u8F7D\u8BC1\u5238...',

    // -- Research Page --
    research_title: '\u7814\u7A76\u5DE5\u4F5C\u53F0',
    research_subtitle: '\u57FA\u4E8E PIT \u7684\u91CF\u5316\u5206\u6790\uFF0C\u4E25\u683C\u63A7\u5236\u65F6\u95F4\u8FB9\u754C',
    research_quick_analysis: '\u5FEB\u901F\u5206\u6790',
    research_select_instrument: '\u9009\u62E9\u8BC1\u5238',
    research_asof_date: '\u622A\u6B62\u65E5\u671F',
    research_load_summary: '\u6982\u89C8',
    research_load_performance: '\u7EE9\u6548',
    research_load_valuation: '\u4F30\u503C',
    research_load_drawdown: '\u56DE\u64A4',
    research_event_study: '\u4E8B\u4EF6\u7814\u7A76',
    research_event_study_desc: '\u8D22\u62A5\u540E\u6536\u76CA\u5206\u6790\uFF081/3/5/10 \u65E5\u7A97\u53E3\uFF09',
    research_run_study: '\u8FD0\u884C\u7814\u7A76',
    research_screeners: '\u7B5B\u9009\u5668',
    research_screener_liquidity: '\u6D41\u52A8\u6027\u7B5B\u9009',
    research_screener_returns: '\u6536\u76CA\u7387\u7B5B\u9009',
    research_screener_fundamentals: '\u57FA\u672C\u9762\u7B5B\u9009',
    research_screener_rank: '\u7EFC\u5408\u6392\u540D',
    research_results: '\u7ED3\u679C',
    research_no_results: '\u8FD0\u884C\u5206\u6790\u4EE5\u67E5\u770B\u7ED3\u679C\u3002',
    research_pit_notice: '\u6240\u6709\u67E5\u8BE2\u5747\u9075\u5B88 PIT \u8FB9\u754C\u3002\u65E0\u672A\u6765\u6570\u636E\u6CC4\u9732\u3002',

    // -- Backtest Page --
    backtest_title: '\u56DE\u6D4B\u5F15\u64CE',
    backtest_subtitle: '\u8FD0\u884C\u3001\u5B58\u50A8\u548C\u5206\u6790\u7B56\u7565\u56DE\u6D4B',
    backtest_new: '\u65B0\u5EFA\u56DE\u6D4B',
    backtest_config: '\u914D\u7F6E',
    backtest_strategy: '\u7B56\u7565',
    backtest_tickers: '\u8BC1\u5238\u4EE3\u7801\uFF08\u9017\u53F7\u5206\u9694\uFF09',
    backtest_start_date: '\u5F00\u59CB\u65E5\u671F',
    backtest_end_date: '\u7ED3\u675F\u65E5\u671F',
    backtest_slippage: '\u6ED1\u70B9\uFF08\u57FA\u70B9\uFF09',
    backtest_max_positions: '\u6700\u5927\u6301\u4ED3',
    backtest_rebalance: '\u518D\u5E73\u8861\u9891\u7387',
    backtest_run: '\u8FD0\u884C\u56DE\u6D4B',
    backtest_cancel: '\u53D6\u6D88',
    backtest_running: '\u6B63\u5728\u8FD0\u884C\u56DE\u6D4B...',
    backtest_past_runs: '\u5386\u53F2\u56DE\u6D4B',
    backtest_no_runs: '\u6682\u65E0\u56DE\u6D4B\u8BB0\u5F55\u3002',
    backtest_detail: '\u56DE\u6D4B\u8BE6\u60C5',
    backtest_metrics: '\u7EE9\u6548\u6307\u6807',
    backtest_trades: '\u4EA4\u6613\u8BB0\u5F55',
    backtest_nav_series: '\u51C0\u503C\u66F2\u7EBF',
    backtest_total_return: '\u603B\u6536\u76CA',
    backtest_ann_return: '\u5E74\u5316\u6536\u76CA',
    backtest_volatility: '\u6CE2\u52A8\u7387',
    backtest_sharpe_ratio: '\u590F\u666E\u6BD4\u7387',
    backtest_max_drawdown: '\u6700\u5927\u56DE\u64A4',
    backtest_total_trades: '\u603B\u4EA4\u6613\u6570',
    backtest_turnover: '\u6362\u624B\u7387',
    backtest_total_costs: '\u603B\u6210\u672C',
    backtest_final_nav: '\u6700\u7EC8\u51C0\u503C',
    backtest_initial_capital: '\u521D\u59CB\u8D44\u672C',
    rebalance_monthly: '\u6BCF\u6708',
    rebalance_weekly: '\u6BCF\u5468',
    rebalance_daily: '\u6BCF\u65E5',
    strategy_momentum: '\u52A8\u91CF\u7B56\u7565',
    strategy_equal_weight: '\u7B49\u6743\u7B56\u7565',

    // -- Execution Page --
    execution_title: '\u6267\u884C\u4E0E\u8BA2\u5355',
    execution_subtitle: '\u53D7\u63A7\u8BA2\u5355\u7BA1\u9053\uFF0C\u5FC5\u987B\u7ECF\u8FC7\u5BA1\u6279\u95E8',
    execution_intents: '\u4EA4\u6613\u610F\u56FE',
    execution_drafts: '\u8BA2\u5355\u8349\u7A3F',
    execution_create_intent: '\u521B\u5EFA\u610F\u56FE',
    execution_strategy_name: '\u7B56\u7565\u540D\u79F0',
    execution_instrument: '\u8BC1\u5238',
    execution_side: '\u65B9\u5411',
    execution_target_qty: '\u76EE\u6807\u6570\u91CF',
    execution_reason: '\u539F\u56E0',
    execution_create: '\u521B\u5EFA\u610F\u56FE',
    execution_policy_notice: '\u5B9E\u76D8\u63D0\u4EA4\u5DF2\u7981\u7528',
    execution_side_buy: '\u4E70\u5165',
    execution_side_sell: '\u5356\u51FA',
    execution_no_intents: '\u6682\u65E0\u4EA4\u6613\u610F\u56FE\u3002\u521B\u5EFA\u4E00\u4E2A\u5F00\u59CB\u3002',
    execution_no_drafts: '\u6682\u65E0\u8BA2\u5355\u8349\u7A3F\u3002',

    // -- DQ Page --
    dq_title: '\u6570\u636E\u8D28\u91CF\u5F15\u64CE',
    dq_subtitle: '11 \u6761\u81EA\u52A8\u5316\u89C4\u5219\uFF0C\u5E26\u6301\u4E45\u5316\u95EE\u9898\u8DDF\u8E2A',
    dq_rules: '\u8D28\u91CF\u89C4\u5219',
    dq_issues: '\u6570\u636E\u95EE\u9898',
    dq_source_runs: '\u91C7\u96C6\u8FD0\u884C\u8BB0\u5F55',
    dq_no_issues: '\u672A\u53D1\u73B0\u6570\u636E\u8D28\u91CF\u95EE\u9898\u3002',
    dq_all_clear: '\u5168\u90E8\u901A\u8FC7',
    dq_rule_names: {
      'DQ-1': 'OHLC \u903B\u8F91',
      'DQ-2': '\u975E\u8D1F\u503C',
      'DQ-3': '\u4E3B\u952E\u91CD\u590D',
      'DQ-4': '\u4EA4\u6613\u65E5',
      'DQ-5': '\u516C\u53F8\u884C\u4E3A',
      'DQ-6': 'PIT \u68C0\u67E5',
      'DQ-7': '\u8DE8\u6E90\u6BD4\u5BF9',
      'DQ-8': '\u6570\u636E\u65AD\u5C42',
      'DQ-9': '\u4EE3\u7801\u91CD\u53E0',
      'DQ-10': '\u5B64\u7ACB\u6807\u8BC6',
      'DQ-11': '\u539F\u59CB/\u8C03\u6574\u6DF7\u5408',
    },

    // -- Settings Page --
    settings_title: '\u914D\u7F6E\u4E0E\u7B56\u7565',
    settings_subtitle: 'API \u5BC6\u94A5\u3001\u529F\u80FD\u5F00\u5173\u548C\u6267\u884C\u7B56\u7565',
    settings_api_keys: 'API \u5BC6\u94A5',
    settings_feature_flags: '\u529F\u80FD\u5F00\u5173',
    settings_execution_policy: '\u6267\u884C\u7B56\u7565',
    settings_data_sources: '\u6570\u636E\u6E90',
    settings_key_names: {
      sec: 'SEC EDGAR',
      openfigi: 'OpenFIGI',
      massive: 'Massive / Polygon',
      fmp: 'Financial Modeling Prep',
      t212: 'Trading 212',
      bea: 'BEA \u7ECF\u6D4E\u5206\u6790\u5C40',
      bls: 'BLS \u52B3\u5DE5\u7EDF\u8BA1\u5C40',
      treasury: '\u7F8E\u56FD\u8D22\u653F\u90E8',
    },

    // -- Log Events --
    log_system_boot: '\u7CFB\u7EDF\u542F\u52A8',
    log_health_check: '\u5065\u5EB7\u68C0\u67E5',
    log_data_loaded: '\u6570\u636E\u52A0\u8F7D',
    log_sync_complete: '\u540C\u6B65\u5B8C\u6210',
    log_sync_error: '\u540C\u6B65\u9519\u8BEF',
    log_nav: '\u5BFC\u822A',
    log_backtest_start: '\u56DE\u6D4B\u5F00\u59CB',
    log_backtest_done: '\u56DE\u6D4B\u5B8C\u6210',
    log_backtest_error: '\u56DE\u6D4B\u9519\u8BEF',
    log_export: '\u5BFC\u51FA',
    log_dashboard_init: '\u4EEA\u8868\u76D8\u5DF2\u521D\u59CB\u5316',
    log_instruments_loaded: '\u53EA\u8BC1\u5238\u5DF2\u52A0\u8F7D',
    log_all_refreshed: '\u6240\u6709\u6570\u636E\u5DF2\u5237\u65B0',
    log_page_loaded: '\u9875\u9762\u5DF2\u52A0\u8F7D',

    // -- Common --
    loading: '\u52A0\u8F7D\u4E2D...',
    error_title: '\u9875\u9762\u52A0\u8F7D\u51FA\u9519',
    retry: '\u91CD\u8BD5',
    cancel: '\u53D6\u6D88',
    confirm: '\u786E\u8BA4',
    close: '\u5173\u95ED',
    save: '\u4FDD\u5B58',
    delete: '\u5220\u9664',
    edit: '\u7F16\u8F91',
    view: '\u67E5\u770B',
    refresh: '\u5237\u65B0',
    no_data: '\u6682\u65E0\u6570\u636E',
    latency: '\u5EF6\u8FDF',
    version: '\u7248\u672C',
  },
};

// ---- Language State ----
let currentLang = localStorage.getItem('quant_lang') || 'zh-CN';

function t(key) {
  const lang = I18N[currentLang] || I18N['en'];
  const val = lang[key];
  if (val !== undefined) return val;
  // Fallback to English
  const enVal = I18N['en'][key];
  if (enVal !== undefined) return enVal;
  return key;
}

function tNested(key, subKey) {
  const lang = I18N[currentLang] || I18N['en'];
  const obj = lang[key];
  if (obj && obj[subKey] !== undefined) return obj[subKey];
  const enObj = I18N['en'][key];
  if (enObj && enObj[subKey] !== undefined) return enObj[subKey];
  return subKey;
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('quant_lang', lang);
  // Re-render the whole app
  const sidebar = document.querySelector('.sidebar');
  if (sidebar && typeof renderSidebar === 'function') {
    sidebar.innerHTML = renderSidebar();
  }
  // Update topbar
  updateTopbarLanguage();
  // Re-render current page
  if (typeof renderPage === 'function') renderPage();
}

function updateTopbarLanguage() {
  const tabs = document.querySelectorAll('.topbar-tabs .tab');
  const tabKeys = ['tab_dashboard', 'tab_instruments', 'tab_research', 'tab_backtests', 'tab_orders'];
  tabs.forEach((tab, i) => {
    if (tabKeys[i]) tab.textContent = t(tabKeys[i]);
  });
  const searchInput = document.querySelector('.search-box input');
  if (searchInput) searchInput.placeholder = t('search_placeholder');
}

function getLangSwitcherHtml() {
  const isZh = currentLang === 'zh-CN';
  return `<div class="lang-switcher" style="display:flex;gap:4px;margin-right:8px;">
    <button onclick="setLanguage('en')" class="icon-btn" style="font-size:12px;font-weight:${isZh ? '500' : '700'};color:${isZh ? 'var(--color-text-muted)' : 'var(--color-primary)'}">EN</button>
    <button onclick="setLanguage('zh-CN')" class="icon-btn" style="font-size:12px;font-weight:${isZh ? '700' : '500'};color:${isZh ? 'var(--color-primary)' : 'var(--color-text-muted)'}">中</button>
  </div>`;
}
