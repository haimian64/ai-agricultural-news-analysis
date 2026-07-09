(function () {
    "use strict";
    const API = "/api";
    // ===== 全国省份城市数据（34个省级行政区，覆盖主要地级市） =====
    const PROVINCE_CITIES = {
        // 直辖市
        "北京市": ["北京市"],
        "天津市": ["天津市"],
        "上海市": ["上海市"],
        "重庆市": ["重庆市"],

        // 河北省（11个地级市）
        "河北省": ["石家庄市", "唐山市", "秦皇岛市", "邯郸市", "邢台市", "保定市", "张家口市", "承德市", "沧州市", "廊坊市", "衡水市"],
        // 山西省（11个地级市）
        "山西省": ["太原市", "大同市", "阳泉市", "长治市", "晋城市", "朔州市", "晋中市", "运城市", "忻州市", "临汾市", "吕梁市"],
        // 辽宁省（14个地级市）
        "辽宁省": ["沈阳市", "大连市", "鞍山市", "抚顺市", "本溪市", "丹东市", "锦州市", "营口市", "阜新市", "辽阳市", "盘锦市", "铁岭市", "朝阳市", "葫芦岛市"],
        // 吉林省（9个地级市/州）
        "吉林省": ["长春市", "吉林市", "四平市", "辽源市", "通化市", "白山市", "松原市", "白城市", "延边朝鲜族自治州"],
        // 黑龙江省（13个地级市/地区）
        "黑龙江省": ["哈尔滨市", "齐齐哈尔市", "鸡西市", "鹤岗市", "双鸭山市", "大庆市", "伊春市", "佳木斯市", "七台河市", "牡丹江市", "黑河市", "绥化市", "大兴安岭地区"],
        // 江苏省（13个地级市）
        "江苏省": ["南京市", "无锡市", "徐州市", "常州市", "苏州市", "南通市", "连云港市", "淮安市", "盐城市", "扬州市", "镇江市", "泰州市", "宿迁市"],
        // 浙江省（11个地级市）
        "浙江省": ["杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", "绍兴市", "金华市", "衢州市", "舟山市", "台州市", "丽水市"],
        // 安徽省（16个地级市）
        "安徽省": ["合肥市", "芜湖市", "蚌埠市", "淮南市", "马鞍山市", "淮北市", "铜陵市", "安庆市", "黄山市", "滁州市", "阜阳市", "宿州市", "六安市", "亳州市", "池州市", "宣城市"],
        // 福建省（9个地级市）
        "福建省": ["福州市", "厦门市", "莆田市", "三明市", "泉州市", "漳州市", "南平市", "龙岩市", "宁德市"],
        // 江西省（11个地级市）
        "江西省": ["南昌市", "景德镇市", "萍乡市", "九江市", "新余市", "鹰潭市", "赣州市", "吉安市", "宜春市", "抚州市", "上饶市"],
        // 山东省（16个地级市）
        "山东省": ["济南市", "青岛市", "淄博市", "枣庄市", "东营市", "烟台市", "潍坊市", "济宁市", "泰安市", "威海市", "日照市", "临沂市", "德州市", "聊城市", "滨州市", "菏泽市"],
        // 河南省（18个地级市）
        "河南省": ["郑州市", "开封市", "洛阳市", "平顶山市", "安阳市", "鹤壁市", "新乡市", "焦作市", "濮阳市", "许昌市", "漯河市", "三门峡市", "南阳市", "商丘市", "信阳市", "周口市", "驻马店市", "济源市"],
        // 湖北省（17个地级市/州）
        "湖北省": ["武汉市", "黄石市", "十堰市", "宜昌市", "襄阳市", "鄂州市", "荆门市", "孝感市", "荆州市", "黄冈市", "咸宁市", "随州市", "恩施土家族苗族自治州", "仙桃市", "潜江市", "天门市", "神农架林区"],
        // 湖南省（14个地级市/州）
        "湖南省": ["长沙市", "株洲市", "湘潭市", "衡阳市", "邵阳市", "岳阳市", "常德市", "张家界市", "益阳市", "郴州市", "永州市", "怀化市", "娄底市", "湘西土家族苗族自治州"],
        // 广东省（21个地级市）
        "广东省": ["广州市", "韶关市", "深圳市", "珠海市", "汕头市", "佛山市", "江门市", "湛江市", "茂名市", "肇庆市", "惠州市", "梅州市", "汕尾市", "河源市", "阳江市", "清远市", "东莞市", "中山市", "潮州市", "揭阳市", "云浮市"],
        // 海南省（4个地级市）
        "海南省": ["海口市", "三亚市", "三沙市", "儋州市"],
        // 四川省（21个地级市/州）
        "四川省": ["成都市", "自贡市", "攀枝花市", "泸州市", "德阳市", "绵阳市", "广元市", "遂宁市", "内江市", "乐山市", "南充市", "眉山市", "宜宾市", "广安市", "达州市", "雅安市", "巴中市", "资阳市", "阿坝藏族羌族自治州", "甘孜藏族自治州", "凉山彝族自治州"],
        // 贵州省（9个地级市/州）
        "贵州省": ["贵阳市", "六盘水市", "遵义市", "安顺市", "毕节市", "铜仁市", "黔西南布依族苗族自治州", "黔东南苗族侗族自治州", "黔南布依族苗族自治州"],
        // 云南省（16个地级市/州）
        "云南省": ["昆明市", "曲靖市", "玉溪市", "保山市", "昭通市", "丽江市", "普洱市", "临沧市", "楚雄彝族自治州", "红河哈尼族彝族自治州", "文山壮族苗族自治州", "西双版纳傣族自治州", "大理白族自治州", "德宏傣族景颇族自治州", "怒江傈僳族自治州", "迪庆藏族自治州"],
        // 陕西省（10个地级市）
        "陕西省": ["西安市", "铜川市", "宝鸡市", "咸阳市", "渭南市", "延安市", "汉中市", "榆林市", "安康市", "商洛市"],
        // 甘肃省（14个地级市/州）
        "甘肃省": ["兰州市", "嘉峪关市", "金昌市", "白银市", "天水市", "武威市", "张掖市", "平凉市", "酒泉市", "庆阳市", "定西市", "陇南市", "临夏回族自治州", "甘南藏族自治州"],
        // 青海省（8个地级市/州）
        "青海省": ["西宁市", "海东市", "海北藏族自治州", "黄南藏族自治州", "海南藏族自治州", "果洛藏族自治州", "玉树藏族自治州", "海西蒙古族藏族自治州"],
        // 台湾省（主要城市）
        "台湾省": ["台北市", "高雄市", "台中市", "台南市", "基隆市", "新竹市", "嘉义市"],
        // 内蒙古自治区（12个地级市/盟）
        "内蒙古自治区": ["呼和浩特市", "包头市", "乌海市", "赤峰市", "通辽市", "鄂尔多斯市", "呼伦贝尔市", "巴彦淖尔市", "乌兰察布市", "兴安盟", "锡林郭勒盟", "阿拉善盟"],
        // 广西壮族自治区（14个地级市）
        "广西壮族自治区": ["南宁市", "柳州市", "桂林市", "梧州市", "北海市", "防城港市", "钦州市", "贵港市", "玉林市", "百色市", "贺州市", "河池市", "来宾市", "崇左市"],
        // 西藏自治区（7个地级市/地区）
        "西藏自治区": ["拉萨市", "日喀则市", "昌都市", "林芝市", "山南市", "那曲市", "阿里地区"],
        // 宁夏回族自治区（5个地级市）
        "宁夏回族自治区": ["银川市", "石嘴山市", "吴忠市", "固原市", "中卫市"],
        // 新疆维吾尔自治区（14个地级市/地区/州）
        "新疆维吾尔自治区": ["乌鲁木齐市", "克拉玛依市", "吐鲁番市", "哈密市", "昌吉回族自治州", "博尔塔拉蒙古自治州", "巴音郭楞蒙古自治州", "阿克苏地区", "克孜勒苏柯尔克孜自治州", "喀什地区", "和田地区", "伊犁哈萨克自治州", "塔城地区", "阿勒泰地区"],
        // 香港特别行政区
        "香港特别行政区": ["香港"],
        // 澳门特别行政区
        "澳门特别行政区": ["澳门"]
    };
    const COLORS = ["#2e86c1", "#27ae60", "#e67e22", "#e74c3c", "#9b59b6", "#95a5a6"];
    const charts = {};
    let currentKeyword = null, currentDateRange = null;

    async function fetchJSON(url) {
        try {
            const r = await fetch(url);
            return await r.json();
        } catch (e) {
            return null;
        }
    }

    function byId(id) {
        return document.getElementById(id);
    }

    function setText(id, v) {
        const el = byId(id);
        if (el) el.textContent = v ?? "--";
    }

    async function loadStatistics() {
        const s = await fetchJSON(API + "/statistics");
        if (!s) return;
        setText("stat-news", s.total_news);
        setText("stat-disasters", s.total_disasters);
        setText("stat-categories", Object.keys(s.category_counts || {}).length);
        const ss = await fetchJSON(API + "/analysis/sentiment-summary");
        if (ss) {
            setText("stat-sentiment-score", ss.score_10);
            const el = byId("stat-sentiment-score");
            if (el) el.style.color = ss.score_10 >= 7 ? "#27ae60" : (ss.score_10 <= 4 ? "#e74c3c" : "#e67e22");
        }
    }

    async function loadCategoryChart(keyword) {
        var cats = {};
        if (keyword) {
            var data = await fetchJSON(API + "/news?keyword=" + encodeURIComponent(keyword) + "&limit=200");
            if (Array.isArray(data)) data.forEach(function (a) {
                var c = a.category || "综合资讯";
                cats[c] = (cats[c] || 0) + 1;
            });
        } else {
            var s = await fetchJSON(API + "/statistics");
            if (s && s.category_counts) cats = s.category_counts;
        }
        if (Object.keys(cats).length === 0) cats = {"综合资讯": 1};
        var entries = Object.entries(cats);
        var chart = echarts.init(byId("chartCategory"));
        chart.setOption({
            tooltip: {trigger: "item", formatter: "{b}: {c} ({d}%)"},
            series: [{
                type: "pie", radius: ["35%", "60%"], center: ["40%", "50%"],
                data: entries.map(function (e, i) {
                    return {name: e[0], value: e[1], itemStyle: {color: COLORS[i % COLORS.length]}};
                })
            }]
        });
        charts.category = chart;
    }

    async function loadSentimentChart(keyword) {
        var counts = {positive: 0, neutral: 0, negative: 0};
        if (keyword) {
            var data = await fetchJSON(API + "/news?keyword=" + encodeURIComponent(keyword) + "&limit=200");
            if (Array.isArray(data)) data.forEach(function (a) {
                var s = a.sentiment || "neutral";
                counts[s] = (counts[s] || 0) + 1;
            });
        } else {
            var a = await fetchJSON(API + "/analysis");
            if (a && a.sentiment_distribution) Object.keys(a.sentiment_distribution).forEach(function (k) {
                counts[k] = a.sentiment_distribution[k].count;
            });
        }
        var total = Object.values(counts).reduce(function (a, b) {
            return a + b;
        }, 0);
        if (total === 0) counts = {positive: 1, neutral: 1, negative: 1};
        var clr = {positive: "#27ae60", neutral: "#95a5a6", negative: "#e74c3c"};
        var lbls = Object.keys(counts).filter(function (k) {
            return counts[k] > 0;
        });
        var ct = echarts.init(byId("chartSentiment"));
        ct.setOption({
            grid: {left: 40, right: 20, top: 20, bottom: 30},
            xAxis: {
                type: "category", data: lbls.map(function (l) {
                    return {"positive": "正面", "neutral": "中性", "negative": "负面"}[l] || l;
                })
            },
            yAxis: {type: "value", minInterval: 1},
            series: [{
                type: "bar", data: lbls.map(function (l) {
                    return {value: counts[l], itemStyle: {color: clr[l] || "#95a5a6", borderRadius: [4, 4, 0, 0]}};
                }), barWidth: 50,
                label: {show: true, position: "top", fontSize: 13, fontWeight: "bold", color: "#333"}
            }]
        });
        charts.sentiment = ct;
    }

    async function loadTrendChart() {
        var r = await fetchJSON(API + "/analysis/trend");
        if (!r || !r.trend || Object.keys(r.trend).length === 0) {
            var el = byId("chartTrend");
            if (el) el.innerHTML = "<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:14px'><div style='font-size:36px;margin-bottom:8px'>📈</div><div>暂无趋势数据</div><div style='font-size:12px;margin-top:4px'>点击「爬取实时新闻」获取</div></div>";
            return;
        }
        var t = r.trend, dates = Object.keys(t).sort(), cats = new Set();
        dates.forEach(function (d) {
            Object.keys(t[d]).forEach(function (c) {
                cats.add(c);
            });
        });
        var cl = Array.from(cats);
        var chart = echarts.init(byId("chartTrend"));
        chart.setOption({
            tooltip: {trigger: "axis"},
            legend: {data: cl, bottom: 0, textStyle: {fontSize: 11}},
            grid: {left: 50, right: 20, bottom: 65, top: 20},
            xAxis: {type: "category", data: dates, axisLabel: {fontSize: 11}},
            yAxis: {type: "value", minInterval: 1},
            dataZoom: [{
                type: "slider",
                start: 0,
                end: 100,
                height: 25,
                bottom: 25,
                handleSize: "80%",
                textStyle: {fontSize: 10}
            }, {
                type: "inside",
                start: 0,
                end: 100,
                zoomOnMouseWheel: true,
                moveOnMouseMove: true
            }],
            series: cl.map(function (c, i) {
                return {
                    name: c, type: "line", smooth: true,
                    lineStyle: {width: 2}, symbolSize: 5, itemStyle: {color: COLORS[i % COLORS.length]},
                    data: dates.map(function (d) {
                        return t[d][c] || 0;
                    })
                }
            })
        });
        charts.trend = chart;
    }

    async function loadKeywords() {
        var r = await fetchJSON(API + "/analysis/hot-keywords");
        var container = byId("keywordCloud");
        if (!container) return;
        if (!r || !r.keywords || r.keywords.length === 0) {
            container.innerHTML = "<div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:160px;color:#aaa;font-size:14px'><div style='font-size:32px;margin-bottom:6px'>🔑</div><div>暂无热点关键词</div><div style='font-size:12px;margin-top:4px'>点击「爬取实时新闻」获取</div></div>";
            return;
        }
        container.innerHTML = "";
        var maxW = Math.max.apply(null, r.keywords.map(function (k) {
            return k.weight;
        }));
        r.keywords.slice(0, 30).forEach(function (kw) {
            var span = document.createElement("span");
            span.textContent = kw.word;
            span.title = kw.word + " - 点击筛选";
            var ratio = kw.weight / maxW;
            span.style.fontSize = (13 + ratio * 20) + "px";
            span.style.fontWeight = ratio > 0.5 ? "700" : "400";
            span.style.opacity = 0.5 + ratio * 0.5;
            span.onclick = function () {
                keywordFilter(kw.word);
            };
            if (currentKeyword === kw.word) span.className = "active";
            container.appendChild(span);
        });
    }

    async function keywordFilter(kw) {
        currentKeyword = (currentKeyword === kw) ? null : kw;
        await Promise.all([loadCategoryChart(currentKeyword), loadSentimentChart(currentKeyword), loadKeywords()]);
        loadNewsList();
        if (currentKeyword) {
            var d = await fetchJSON(API + "/news?keyword=" + encodeURIComponent(currentKeyword) + (currentDateRange ? "&start_date=" + currentDateRange.start + "&end_date=" + currentDateRange.end : ""));
            renderNewsList(d, "keywordNewsList");
            byId("keywordNewsRow").style.display = "";
            byId("keywordNewsTitle").textContent = "— 关键词: " + currentKeyword;
        } else {
            byId("keywordNewsRow").style.display = "none";
        }
    }

    function getDefaultDates() {
        var now = new Date();
        var start = new Date(now);
        start.setFullYear(start.getFullYear() - 1);

        function pad(n) {
            return String(n).padStart(2, "0");
        }

        return {
            start: start.getFullYear() + "-" + pad(start.getMonth() + 1) + "-" + pad(start.getDate()),
            end: now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate())
        };
    }

    async function applyDateFilter() {
        var sd = byId("startDate").value, ed = byId("endDate").value;
        if (sd && ed && sd <= ed) currentDateRange = {start: sd, end: ed};
        await loadNewsList();
    }

    function resetDateFilter() {
        currentDateRange = null;
        var d = getDefaultDates();
        byId("startDate").value = d.start;
        byId("endDate").value = d.end;
        loadNewsList();
    }

    async function loadNewsList() {
        var url = API + "/news?limit=30";
        if (currentDateRange) url += "&start_date=" + currentDateRange.start + "&end_date=" + currentDateRange.end;
        var data = await fetchJSON(url);
        renderNewsList(data, "newsList");
    }

    function renderNewsList(data, containerId) {
        var container = byId(containerId);
        if (!container) return;
        if (!data || !data.length) {
            container.innerHTML = "<div style='padding:20px;text-align:center;color:#888'>暂无数据</div>";
            return;
        }
        container.innerHTML = data.map(function (a) {
            var url = a.url || "", title = a.title || "无标题", date = (a.date || "").slice(0, 10);
            var cat = a.category || "", src = a.source || "";
            var linkHtml = url ? "<a href='" + url + "' target='_blank'>" + title + "</a>" : title;
            return "<div class='news-item'><span class='news-date'>" + date + "</span><span class='news-cat'>" + cat + "</span><span class='news-title'>" + linkHtml + "</span><span class='news-source'>" + src + "</span></div>";
        }).join("");
    }

    async function loadDisasters() {
        var d = await fetchJSON(API + "/disasters");
        if (!d) return;
        var container = byId("disasterList");
        if (!container) return;
        var lc = {1: "level-1", 2: "level-2", 3: "level-3", 4: "level-4"};
        var bc = {1: "badge-red", 2: "badge-orange", 3: "badge-yellow", 4: "badge-blue"};
        var ll = {1: "红色", 2: "橙色", 3: "黄色", 4: "蓝色"};
        container.innerHTML = d.length ? d.map(function (x) {
            var sev = x.severity || 99;
            var lvl = sev <= 4 ? sev : 99;
            var url = x.url || "";
            var title = x.title || "未知";
            var titleHtml = url ? "<a href='" + url + "' target='_blank' class='disaster-title-link' title='点击查看详情'>" + title + "</a>" : title;
            var desc = x.description ? "<div class='disaster-desc'>" + (x.description || "").slice(0, 120) + "</div>" : "";
            var dtype = x.disaster_type ? "<span class='disaster-type-tag'>" + x.disaster_type + "</span>" : "";
            return "<div class='disaster-item " + (lc[lvl] || "") + "'>" +
                "<div class='info'>" +
                "<div class='title'>" + titleHtml + "</div>" +
                "<div class='meta'>" + (x.source || "") + " | " + (x.date || "").slice(0, 10) + " | " + (x.region || "") + dtype + "</div>" +
                desc +
                "</div>" +
                "<span class='badge " + (bc[lvl] || "badge-blue") + "'>" + (ll[lvl] || x.alert_level || "未知") + "</span>" +
                "</div>";
        }).join("") : "<div style='padding:30px;text-align:center;color:#888'>暂无灾害预警数据</div>";
    }

    function fixUrl(url) {
        if (!url) return "#";
        if (url.startsWith("http")) return url;
        return "https://www.agri.cn" + url;
    }

    async function loadMarket() {
        var data = await fetchJSON(API + "/market");
        if (!data) return;
        var container = byId("marketList");
        if (!container) return;
        if (data.items && data.items.length) {
            container.innerHTML = data.items.map(function (item, idx) {
                var href = fixUrl(item.url);
                var src = item.source || "农信网";
                return "<div class='market-item'>" +
                    "<div class='market-num'>" + (idx + 1) + "</div>" +
                    "<div class='market-body'>" +
                    "<div class='market-title'><a href='" + href + "' target='_blank'>" + item.title + "</a></div>" +
                    "<div class='market-meta'><span class='market-source'>" + src + "</span></div>" +
                    "</div>" +
                    "</div>";
            }).join("");
        } else {
            container.innerHTML = "<div class='market-empty'><div class='empty-icon'>📊</div><div>暂无市场数据</div><div class='empty-hint'>点击「爬取实时新闻」获取最新市场动态</div></div>";
        }
    }

    function initWeather() {
        // 填充省份下拉框
        var provinceSel = document.getElementById("weatherProvince");
        var provinces = Object.keys(PROVINCE_CITIES).sort();
        provinces.forEach(function (p) {
            var opt = document.createElement("option");
            opt.value = p;
            opt.textContent = p;
            provinceSel.appendChild(opt);
        });

        // 省份变化 -> 更新城市列表
        provinceSel.onchange = function () {
            var citySel = document.getElementById("weatherCity");
            var selectedProvince = this.value;
            citySel.innerHTML = '<option value="">-- 请选择城市 --</option>';
            if (selectedProvince && PROVINCE_CITIES[selectedProvince]) {
                var cities = PROVINCE_CITIES[selectedProvince];
                cities.forEach(function (c) {
                    var opt = document.createElement("option");
                    opt.value = c;
                    opt.textContent = c;
                    citySel.appendChild(opt);
                });
            }
            // 自动加载第一个城市
            if (citySel.options.length > 1) {
                citySel.selectedIndex = 1;
                loadWeather();
            }
        };

        // 城市变化 -> 加载天气
        document.getElementById("weatherCity").onchange = function () {
            if (this.value) loadWeather();
        };

        // 默认选中第一个省份（河南省）
        if (provinceSel.options.length > 0) {
            // 尝试选中河南省
            for (var i = 0; i < provinceSel.options.length; i++) {
                if (provinceSel.options[i].value === "河南省") {
                    provinceSel.selectedIndex = i;
                    break;
                }
            }
            if (provinceSel.selectedIndex === 0) provinceSel.selectedIndex = 1;
            provinceSel.onchange();
        }
    }

    // Tab Switching
    document.querySelectorAll(".tab-btn").forEach(function (btn) {
        btn.onclick = function () {
            document.querySelectorAll(".tab-btn").forEach(function (b) {
                b.classList.remove("active");
            });
            document.querySelectorAll(".tab-content").forEach(function (t) {
                t.style.display = "none";
            });
            btn.classList.add("active");
            var tab = document.getElementById("tab" + btn.dataset.tab.charAt(0).toUpperCase() + btn.dataset.tab.slice(1));
            if (tab) tab.style.display = "";
            if (btn.dataset.tab === "weather") loadWeather();
            if (btn.dataset.tab === "market") loadMarket();
            if (btn.dataset.tab === "disaster") loadDisasters();
        };
    });

    // Weather
    var wmoDesc = {
        0: "晴天",
        1: "多云",
        2: "阴天",
        3: "阴天",
        45: "有雾",
        48: "有雾",
        51: "毛毛雨",
        61: "有雨",
        71: "有雪",
        95: "雷暴"
    };
    var wmoIcon = {0: "☀️", 1: "⛅", 2: "☁️", 3: "☁️", 45: "🌫️", 61: "🌧️", 71: "❄️", 95: "⛈️"};

    function wmoCode(c) {
        return wmoDesc[c] || "";
    }

    function wmoIco(c) {
        return wmoIcon[c] || "☁️";
    }

    async function loadWeather() {
        var city = document.getElementById("weatherCity").value;
        if (!city) {
            byId("weatherCurrent").innerHTML = "<div class='weather-empty'>请选择城市</div>";
            byId("weatherForecast").innerHTML = "";
            return;
        }
        var data = await fetchJSON(API + "/weather?city=" + encodeURIComponent(city));
        if (!data || !data.current) {
            byId("weatherCurrent").innerHTML = "<div class='weather-empty'>暂无天气数据</div>";
            byId("weatherForecast").innerHTML = "";
            return;
        }
        var cur = data.current;
        var wc = cur.weathercode || 0;
        var desc = wmoCode(wc) || "";
        var icon = wmoIco(wc);
        // 当前天气大卡片
        byId("weatherCurrent").innerHTML =
            "<div class='weather-current-card'>" +
            "<div class='weather-city-name'>" + city + "</div>" +
            "<div class='weather-temp-row'><span class='weather-temp-big'>" + cur.temperature + "</span><span class='weather-temp-unit'>°C</span></div>" +
            "<div class='weather-icon-big'>" + icon + "</div>" +
            "<div class='weather-desc'>" + desc + "</div>" +
            "<div class='weather-wind'>风速 " + (cur.windspeed || 0) + " km/h</div>" +
            "</div>";
        // 7天预报
        var daily = data.daily;
        if (daily && daily.time) {
            var weekDays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
            var html2 = daily.time.map(function (t, i) {
                var hi = (daily.temperature_2m_max || [])[i] || "-";
                var lo = (daily.temperature_2m_min || [])[i] || "-";
                var rain = (daily.precipitation_sum || [])[i];
                var wc2 = (daily.weathercode || [])[i] || 0;
                var d = new Date(t);
                var dayLabel = (i === 0) ? "今天" : weekDays[d.getDay()];
                return "<div class='weather-day'>" +
                    "<div class='wd-day'>" + dayLabel + "</div>" +
                    "<div class='wd-date'>" + t.slice(5) + "</div>" +
                    "<div class='wd-icon'>" + wmoIco(wc2) + "</div>" +
                    "<div class='wd-desc'>" + (wmoCode(wc2) || "") + "</div>" +
                    "<div class='wd-temp'><span class='wd-high'>" + hi + "°</span> / <span class='wd-low'>" + lo + "°</span></div>" +
                    (rain > 0 ? "<div class='wd-rain'>💧 " + rain + "mm</div>" : "<div class='wd-rain'>—</div>") +
                    "</div>";
            }).join("");
            byId("weatherForecast").innerHTML = html2;
        }
    }

    document.getElementById("btnRefreshWeather").onclick = loadWeather;
    document.getElementById("weatherCity").onchange = loadWeather;

    // Crawl: fetch real news
    window.startCrawl = async function () {
        var btn = byId("btnCrawl");
        if (!btn) return;
        btn.disabled = true;
        btn.textContent = "⏳ 爬取中...";
        btn.style.opacity = "0.6";

        // 获取日期范围
        var startDate = document.getElementById('startDate').value;
        var endDate = document.getElementById('endDate').value;
        var url = API + "/crawl";
        if (startDate && endDate) {
            url += "?start_date=" + encodeURIComponent(startDate) + "&end_date=" + encodeURIComponent(endDate);
        }

        try {
            var result = await fetchJSON(url);
            if (result) {
                setText("statusText", "已爬取 " + (result.crawled || 0) + " 条, 共 " + (result.total || 0) + " 条");
                // Refresh all data
                await Promise.all([
                    loadStatistics(), loadCategoryChart(), loadSentimentChart(),
                    loadTrendChart(), loadKeywords(), loadDisasters(),
                    loadNewsList(), loadMarket()
                ]);
                btn.textContent = "✅ 爬取完成 (" + (result.crawled || 0) + "条)";
                setTimeout(function () {
                    btn.textContent = "🔄 爬取实时新闻";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    setText("statusText", "系统运行中");
                }, 3000);
            } else {
                btn.textContent = "❌ 爬取失败";
                setTimeout(function () {
                    btn.textContent = "🔄 爬取实时新闻";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                }, 2000);
            }
        } catch (e) {
            btn.textContent = "❌ 出错";
            btn.disabled = false;
            btn.style.opacity = "1";
            setTimeout(function () {
                btn.textContent = "🔄 爬取实时新闻";
            }, 2000);
        }
    };

    // Init
    async function init() {
        var d = getDefaultDates();
        byId("startDate").value = d.start;
        byId("endDate").value = d.end;
        byId("btnFilter").onclick = applyDateFilter;
        byId("btnReset").onclick = resetDateFilter;
        byId("btnKeywords").onclick = async function () {
            currentKeyword = null;
            await keywordFilter(null);
        };
        byId("btnCloseKeywordNews").onclick = async function () {
            currentKeyword = null;
            byId("keywordNewsRow").style.display = "none";
            await keywordFilter(null);
        };
        byId("btnMarket").onclick = loadMarket;
        byId("btnRefreshDisasters").onclick = loadDisasters;
        await Promise.all([
            loadStatistics(), loadCategoryChart(), loadSentimentChart(),
            loadTrendChart(), loadKeywords(), loadDisasters(), loadNewsList(), loadMarket()
        ]);
        initWeather();
        setInterval(function () {
            loadStatistics();
            loadDisasters();
        }, 120000);
    }

    document.addEventListener("DOMContentLoaded", init);
})();