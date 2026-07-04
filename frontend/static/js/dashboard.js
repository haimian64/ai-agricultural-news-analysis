(function() {
    "use strict";
    const API = "/api";
    const COLORS = ["#2e86c1","#27ae60","#e67e22","#e74c3c","#9b59b6","#95a5a6"];
    const charts = {};
    let currentKeyword = null, currentDateRange = null;

    async function fetchJSON(url) {
        try { const r = await fetch(url); return await r.json(); }
        catch(e) { return null; }
    }

    function byId(id) { return document.getElementById(id); }
    function setText(id, v) { const el = byId(id); if(el) el.textContent = v ?? "--"; }

    async function loadStatistics() {
        const s = await fetchJSON(API+"/statistics");
        if(!s) return;
        setText("stat-news", s.total_news);
        setText("stat-disasters", s.total_disasters);
        setText("stat-categories", Object.keys(s.category_counts||{}).length);
        const ss = await fetchJSON(API+"/analysis/sentiment-summary");
        if(ss) {
            setText("stat-sentiment-score", ss.score_10);
            const el = byId("stat-sentiment-score");
            if(el) el.style.color = ss.score_10>=7 ? "#27ae60" : (ss.score_10<=4 ? "#e74c3c" : "#e67e22");
        }
    }

    async function loadCategoryChart(keyword) {
        var cats = {};
        if(keyword) {
            var data = await fetchJSON(API+"/news?keyword="+encodeURIComponent(keyword)+"&limit=200");
            if(Array.isArray(data)) data.forEach(function(a){var c=a.category||"综合资讯";cats[c]=(cats[c]||0)+1;});
        } else {
            var s = await fetchJSON(API+"/statistics");
            if(s && s.category_counts) cats = s.category_counts;
        }
        if(Object.keys(cats).length===0) cats={"综合资讯":1};
        var entries = Object.entries(cats);
        var chart = echarts.init(byId("chartCategory"));
        chart.setOption({
            tooltip:{trigger:"item",formatter:"{b}: {c} ({d}%)"},
            series:[{type:"pie",radius:["35%","60%"],center:["40%","50%"],
                data:entries.map(function(e,i){return{name:e[0],value:e[1],itemStyle:{color:COLORS[i%COLORS.length]}};})}]
        });
        charts.category = chart;
    }

    async function loadSentimentChart(keyword) {
        var counts = {positive:0,neutral:0,negative:0};
        if(keyword) {
            var data = await fetchJSON(API+"/news?keyword="+encodeURIComponent(keyword)+"&limit=200");
            if(Array.isArray(data)) data.forEach(function(a){var s=a.sentiment||"neutral";counts[s]=(counts[s]||0)+1;});
        } else {
            var a = await fetchJSON(API+"/analysis");
            if(a && a.sentiment_distribution) Object.keys(a.sentiment_distribution).forEach(function(k){counts[k]=a.sentiment_distribution[k].count;});
        }
        var total = Object.values(counts).reduce(function(a,b){return a+b;},0);
        if(total===0) counts={positive:1,neutral:1,negative:1};
        var clr = {positive:"#27ae60",neutral:"#95a5a6",negative:"#e74c3c"};
        var lbls = Object.keys(counts).filter(function(k){return counts[k]>0;});
        var ct = echarts.init(byId("chartSentiment"));
        ct.setOption({
            grid:{left:40,right:20,top:20,bottom:30},
            xAxis:{type:"category",data:lbls.map(function(l){return{"positive":"正面","neutral":"中性","negative":"负面"}[l]||l;})},
            yAxis:{type:"value",minInterval:1},
            series:[{type:"bar",data:lbls.map(function(l){return{value:counts[l],itemStyle:{color:clr[l]||"#95a5a6",borderRadius:[4,4,0,0]}};}),barWidth:50}]
        });
        charts.sentiment = ct;
    }

    async function loadTrendChart() {
        var r = await fetchJSON(API+"/analysis/trend");
        if(!r||!r.trend||Object.keys(r.trend).length===0) {
            var el = byId("chartTrend");
            if(el) el.innerHTML = "<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:14px'><div style='font-size:36px;margin-bottom:8px'>📈</div><div>暂无趋势数据</div><div style='font-size:12px;margin-top:4px'>点击「爬取实时新闻」获取</div></div>";
            return;
        }
        var t = r.trend, dates = Object.keys(t).sort(), cats = new Set();
        dates.forEach(function(d){Object.keys(t[d]).forEach(function(c){cats.add(c);});});
        var cl = Array.from(cats);
        var chart = echarts.init(byId("chartTrend"));
        chart.setOption({tooltip:{trigger:"axis"},
            legend:{data:cl,bottom:0,textStyle:{fontSize:11}},
            grid:{left:50,right:20,bottom:50,top:20},
            xAxis:{type:"category",data:dates,axisLabel:{fontSize:11}},
            yAxis:{type:"value",minInterval:1},
            series:cl.map(function(c,i){return{name:c,type:"line",smooth:true,
                lineStyle:{width:2},symbolSize:5,itemStyle:{color:COLORS[i%COLORS.length]},
                data:dates.map(function(d){return t[d][c]||0;})}})
        });
        charts.trend = chart;
    }

    async function loadKeywords() {
        var r = await fetchJSON(API+"/analysis/hot-keywords");
        var container = byId("keywordCloud"); if(!container) return;
        if(!r||!r.keywords||r.keywords.length===0) {
            container.innerHTML = "<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:160px;color:#aaa;font-size:14px'><div style='font-size:32px;margin-bottom:6px'>🔑</div><div>暂无热点关键词</div><div style='font-size:12px;margin-top:4px'>点击「爬取实时新闻」获取</div></div>";
            return;
        }
        container.innerHTML = "";
        var maxW = Math.max.apply(null, r.keywords.map(function(k){return k.weight;}));
        r.keywords.slice(0,30).forEach(function(kw){
            var span = document.createElement("span");
            span.textContent = kw.word;
            span.title = kw.word+" - 点击筛选";
            var ratio = kw.weight/maxW;
            span.style.fontSize = (13+ratio*20)+"px";
            span.style.fontWeight = ratio>0.5?"700":"400";
            span.style.opacity = 0.5+ratio*0.5;
            span.onclick = function(){ keywordFilter(kw.word); };
            if(currentKeyword===kw.word) span.className="active";
            container.appendChild(span);
        });
    }

    async function keywordFilter(kw) {
        currentKeyword = (currentKeyword===kw) ? null : kw;
        await Promise.all([loadCategoryChart(currentKeyword),loadSentimentChart(currentKeyword),loadKeywords()]);
        loadNewsList();
        if(currentKeyword) {
            var d = await fetchJSON(API+"/news?keyword="+encodeURIComponent(currentKeyword)+(currentDateRange?"&start_date="+currentDateRange.start+"&end_date="+currentDateRange.end:""));
            renderNewsList(d,"keywordNewsList");
            byId("keywordNewsRow").style.display = "";
            byId("keywordNewsTitle").textContent = "— 关键词: "+currentKeyword;
        } else {
            byId("keywordNewsRow").style.display = "none";
        }
    }

    function getDefaultDates() {
        var now = new Date(); var start = new Date(now); start.setFullYear(start.getFullYear()-1);
        function pad(n){return String(n).padStart(2,"0");}
        return {start:start.getFullYear()+"-"+pad(start.getMonth()+1)+"-"+pad(start.getDate()),
                end:now.getFullYear()+"-"+pad(now.getMonth()+1)+"-"+pad(now.getDate())};
    }
    async function applyDateFilter() {
        var sd=byId("startDate").value, ed=byId("endDate").value;
        if(sd&&ed&&sd<=ed) currentDateRange={start:sd,end:ed};
        await loadNewsList();
    }
    function resetDateFilter() {
        currentDateRange=null; var d=getDefaultDates();
        byId("startDate").value=d.start; byId("endDate").value=d.end;
        loadNewsList();
    }

    async function loadNewsList() {
        var url = API+"/news?limit=30";
        if(currentDateRange) url += "&start_date="+currentDateRange.start+"&end_date="+currentDateRange.end;
        var data = await fetchJSON(url);
        renderNewsList(data,"newsList");
    }

    function renderNewsList(data, containerId) {
        var container = byId(containerId);
        if(!container) return;
        if(!data||!data.length) { container.innerHTML="<div style='padding:20px;text-align:center;color:#888'>暂无数据</div>"; return; }
        container.innerHTML = data.map(function(a){
            var url=a.url||"", title=a.title||"无标题", date=(a.date||"").slice(0,10);
            var cat=a.category||"", src=a.source||"";
            var linkHtml = url ? "<a href='"+url+"' target='_blank'>"+title+"</a>" : title;
            return "<div class='news-item'><span class='news-date'>"+date+"</span><span class='news-cat'>"+cat+"</span><span class='news-title'>"+linkHtml+"</span><span class='news-source'>"+src+"</span></div>";
        }).join("");
    }

    async function loadDisasters() {
        var d = await fetchJSON(API+"/disasters"); if(!d) return;
        var container = byId("disasterList"); if(!container) return;
        var lc={1:"level-1",2:"level-2",3:"level-3",4:"level-4"};
        var bc={1:"badge-red",2:"badge-orange",3:"badge-yellow",4:"badge-blue"};
        var ll={1:"红色",2:"橙色",3:"黄色",4:"蓝色"};
        container.innerHTML = d.length ? d.map(function(x){
            var sev=x.severity||99; var lvl=sev<=4?sev:99;
            var url=x.url||"";
            var title=x.title||"未知";
            var titleHtml = url ? "<a href='"+url+"' target='_blank' class='disaster-title-link' title='点击查看详情'>"+title+"</a>" : title;
            var desc = x.description ? "<div class='disaster-desc'>"+(x.description||"").slice(0,120)+"</div>" : "";
            var dtype = x.disaster_type ? "<span class='disaster-type-tag'>"+x.disaster_type+"</span>" : "";
            return "<div class='disaster-item "+(lc[lvl]||"")+"'>" +
                "<div class='info'>" +
                    "<div class='title'>"+titleHtml+"</div>" +
                    "<div class='meta'>"+(x.source||"")+" | "+(x.date||"").slice(0,10)+" | "+(x.region||"")+dtype+"</div>" +
                    desc +
                "</div>" +
                "<span class='badge "+(bc[lvl]||"badge-blue")+"'>"+(ll[lvl]||x.alert_level||"未知")+"</span>" +
            "</div>";
        }).join("") : "<div style='padding:30px;text-align:center;color:#888'>暂无灾害预警数据</div>";
    }

    function fixUrl(url) {
        if(!url) return "#";
        if(url.startsWith("http")) return url;
        return "https://www.agri.cn"+url;
    }
    async function loadMarket() {
        var data = await fetchJSON(API+"/market"); if(!data) return;
        var container = byId("marketList"); if(!container) return;
        if(data.items&&data.items.length) {
            container.innerHTML = data.items.map(function(item, idx){
                var href = fixUrl(item.url);
                var src = item.source || "农信网";
                return "<div class='market-item'>" +
                    "<div class='market-num'>"+(idx+1)+"</div>" +
                    "<div class='market-body'>" +
                        "<div class='market-title'><a href='"+href+"' target='_blank'>"+item.title+"</a></div>" +
                        "<div class='market-meta'><span class='market-source'>"+src+"</span></div>" +
                    "</div>" +
                "</div>";
            }).join("");
        } else {
            container.innerHTML = "<div class='market-empty'><div class='empty-icon'>📊</div><div>暂无市场数据</div><div class='empty-hint'>点击「爬取实时新闻」获取最新市场动态</div></div>";
        }
    }

    function initWeather() {
        // 天气已通过 loadWeather() 和下方事件绑定实现
    }

    // Tab Switching
    document.querySelectorAll(".tab-btn").forEach(function(btn) {
        btn.onclick = function() {
            document.querySelectorAll(".tab-btn").forEach(function(b){b.classList.remove("active");});
            document.querySelectorAll(".tab-content").forEach(function(t){t.style.display="none";});
            btn.classList.add("active");
            var tab = document.getElementById("tab"+btn.dataset.tab.charAt(0).toUpperCase()+btn.dataset.tab.slice(1));
            if(tab) tab.style.display = "";
            if(btn.dataset.tab==="weather") loadWeather();
            if(btn.dataset.tab==="market") loadMarket();
            if(btn.dataset.tab==="disaster") loadDisasters();
        };
    });

    // Weather
    var wmoDesc = {0:"晴天",1:"多云",2:"阴天",3:"阴天",45:"有雾",48:"有雾",51:"毛毛雨",61:"有雨",71:"有雪",95:"雷暴"};
    var wmoIcon = {0:"☀️",1:"⛅",2:"☁️",3:"☁️",45:"🌫️",61:"🌧️",71:"❄️",95:"⛈️"};
    function wmoCode(c) { return wmoDesc[c]||""; }
    function wmoIco(c) { return wmoIcon[c]||"☁️"; }
    async function loadWeather() {
        var city = document.getElementById("weatherCity").value;
        var data = await fetchJSON(API+"/weather?city="+encodeURIComponent(city));
        if(!data||!data.current) {
            byId("weatherCurrent").innerHTML = "<div class='weather-empty'>暂无天气数据</div>";
            byId("weatherForecast").innerHTML = "";
            return;
        }
        var cur = data.current;
        var wc = cur.weathercode||0;
        var desc = wmoCode(wc)||"";
        var icon = wmoIco(wc);
        // 当前天气大卡片
        byId("weatherCurrent").innerHTML =
            "<div class='weather-current-card'>" +
                "<div class='weather-city-name'>"+city+"</div>" +
                "<div class='weather-temp-row'><span class='weather-temp-big'>"+cur.temperature+"</span><span class='weather-temp-unit'>°C</span></div>" +
                "<div class='weather-icon-big'>"+icon+"</div>" +
                "<div class='weather-desc'>"+desc+"</div>" +
                "<div class='weather-wind'>风速 "+(cur.windspeed||0)+" km/h</div>" +
            "</div>";
        // 7天预报
        var daily = data.daily;
        if(daily&&daily.time) {
            var weekDays = ["周日","周一","周二","周三","周四","周五","周六"];
            var now = new Date();
            var html2 = daily.time.map(function(t,i){
                var hi = (daily.temperature_2m_max||[])[i]||"-";
                var lo = (daily.temperature_2m_min||[])[i]||"-";
                var rain = (daily.precipitation_sum||[])[i];
                var wc2 = (daily.weathercode||[])[i]||0;
                // 显示周几
                var d = new Date(t);
                var dayLabel = (i===0) ? "今天" : weekDays[d.getDay()];
                return "<div class='weather-day'>" +
                    "<div class='wd-day'>"+dayLabel+"</div>" +
                    "<div class='wd-date'>"+t.slice(5)+"</div>" +
                    "<div class='wd-icon'>"+wmoIco(wc2)+"</div>" +
                    "<div class='wd-desc'>"+(wmoCode(wc2)||"")+"</div>" +
                    "<div class='wd-temp'><span class='wd-high'>"+hi+"°</span> / <span class='wd-low'>"+lo+"°</span></div>" +
                    (rain>0 ? "<div class='wd-rain'>💧 "+rain+"mm</div>":"<div class='wd-rain'>—</div>") +
                "</div>";
            }).join("");
            byId("weatherForecast").innerHTML = html2;
        }
    }
    document.getElementById("btnRefreshWeather").onclick = loadWeather;
    document.getElementById("weatherCity").onchange = loadWeather;

    // Crawl: fetch real news
    window.startCrawl = async function() {
        var btn = byId("btnCrawl");
        if(!btn) return;
        btn.disabled = true;
        btn.textContent = "⏳ 爬取中...";
        btn.style.opacity = "0.6";
        try {
            var result = await fetchJSON(API+"/crawl");
            if(result) {
                setText("statusText", "已爬取 "+(result.crawled||0)+" 条, 共 "+(result.total||0)+" 条");
                // Refresh all data
                await Promise.all([
                    loadStatistics(), loadCategoryChart(), loadSentimentChart(),
                    loadTrendChart(), loadKeywords(), loadDisasters(),
                    loadNewsList(), loadMarket()
                ]);
                btn.textContent = "✅ 爬取完成 ("+(result.crawled||0)+"条)";
                setTimeout(function(){
                    btn.textContent = "🔄 爬取实时新闻";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    setText("statusText", "系统运行中");
                }, 3000);
            } else {
                btn.textContent = "❌ 爬取失败";
                setTimeout(function(){
                    btn.textContent = "🔄 爬取实时新闻";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                }, 2000);
            }
        } catch(e) {
            btn.textContent = "❌ 出错";
            btn.disabled = false;
            btn.style.opacity = "1";
            setTimeout(function(){btn.textContent="🔄 爬取实时新闻";}, 2000);
        }
    };

    // Init
    async function init() {
        var d=getDefaultDates();
        byId("startDate").value=d.start; byId("endDate").value=d.end;
        byId("btnFilter").onclick=applyDateFilter;
        byId("btnReset").onclick=resetDateFilter;
        byId("btnKeywords").onclick=async function(){currentKeyword=null;await keywordFilter(null);};
        byId("btnCloseKeywordNews").onclick=async function(){currentKeyword=null;byId("keywordNewsRow").style.display="none";await keywordFilter(null);};
        byId("btnMarket").onclick=loadMarket;
        byId("btnRefreshDisasters").onclick=loadDisasters;
        await Promise.all([
            loadStatistics(),loadCategoryChart(),loadSentimentChart(),
            loadTrendChart(),loadKeywords(),loadDisasters(),loadNewsList(),loadMarket()
        ]);
        initWeather();
        setInterval(function(){loadStatistics();loadDisasters();},120000);
    }
    document.addEventListener("DOMContentLoaded", init);
})();