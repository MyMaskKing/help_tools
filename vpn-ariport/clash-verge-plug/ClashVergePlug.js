function main(config) {


    /****************************************
     * 全局配置
     ****************************************/

    const SETTINGS = {


        //测速地址
        testUrl:
            "https://cp.cloudflare.com/generate_204",


        //测速周期
        interval:
            300,


        //允许延迟差
        tolerance:
            80,


        //排除国内节点
        excludeCN:
            /香港|🇭🇰|HK|Hong\s*Kong|台湾|🇹🇼|🇨🇳|TW|Taiwan|中国|CN|China|内地/i

    };



    /****************************************
     * 地区规则
     *
     * 顺序 = 容灾优先级
     ****************************************/

    const REGION_RULES = {


        "🇯🇵 日本自动":

            [
                "日本",
                "🇯🇵",
                "JP",
                "Japan",
                "东京",
                "大阪"
            ],



        "🇸🇬 新加坡自动":

            [
                "新加坡",
                "🇸🇬",
                "SG",
                "Singapore"
            ],



        "🇰🇷 韩国自动":

            [
                "韩国",
                "🇰🇷",
                "KR",
                "Korea",
                "首尔"
            ],



        "🇺🇸 美国自动":

            [
                "美国",
                "🇺🇸",
                "US",
                "USA"
            ]

    };




    /****************************************
     * 获取节点
     ****************************************/

    const allNodes =
        (config.proxies || [])
            .map(p => p.name);



    if(!allNodes.length){

        return config;

    }




    /****************************************
     * 清理节点
     ****************************************/

    const blacklist = [

        "剩余",
        "流量",
        "官网",
        "订阅",
        "套餐",
        "到期",
        "重置",
        "DIRECT",
        "REJECT"

    ];



    const nodes =
        allNodes.filter(name => {


            return !blacklist.some(k =>

                name.includes(k)

            );


        });



    const oldGroups =
        config["proxy-groups"] || [];



    const newGroups = [];





    /****************************************
     * 创建地区 url-test 组
     ****************************************/


    Object.entries(REGION_RULES)
        .forEach(([groupName, keywords]) => {



            const matched =
                nodes.filter(node => {


                    return keywords.some(k =>

                        node
                            .toLowerCase()
                            .includes(
                                k.toLowerCase()
                            )

                    );


                });



            //没有节点跳过

            if(!matched.length){

                return;

            }



            //已存在跳过

            if(
                oldGroups.some(
                    g => g.name === groupName
                )
            ){

                return;

            }



            newGroups.push({


                name:
                groupName,


                type:
                    "url-test",


                proxies:
                matched,


                url:
                SETTINGS.testUrl,


                interval:
                SETTINGS.interval,


                tolerance:
                SETTINGS.tolerance


            });



        });






    /****************************************
     * 创建 🌍 国外自动
     *
     * 所有国外节点测速
     ****************************************/


    const overseasNodes =
        nodes.filter(node => {


            return !SETTINGS.excludeCN.test(node);


        });




    if(

        overseasNodes.length &&

        !oldGroups.some(
            g => g.name === "🌍 国外自动"
        )

    ){


        newGroups.push({


            name:
                "🌍 国外自动",


            type:
                "url-test",


            proxies:
            overseasNodes,


            url:
            SETTINGS.testUrl,


            interval:
            SETTINGS.interval,


            tolerance:
            SETTINGS.tolerance


        });


    }





    /****************************************
     * 创建 🌍 国外容灾
     *
     * 顺序：
     *
     * REGION_RULES
     *
     * ↓
     *
     * 国外自动
     ****************************************/


    const tempGroups = [

        ...oldGroups,

        ...newGroups

    ];



    const fallbackNodes = [];




    // 先加入地区自动组

    Object.keys(REGION_RULES)
        .forEach(name => {


            if(
                tempGroups.some(
                    g => g.name === name
                )
            ){

                fallbackNodes.push(name);

            }


        });





    // 最后加入国外自动兜底

    if(

        tempGroups.some(
            g => g.name === "🌍 国外自动"
        )

    ){

        fallbackNodes.push(
            "🌍 国外自动"
        );

    }





    if(

        fallbackNodes.length &&

        !tempGroups.some(
            g => g.name === "🌍 国外容灾"
        )

    ){


        newGroups.push({


            name:
                "🌍 国外容灾",


            type:
                "fallback",


            proxies:
            fallbackNodes,


            url:
            SETTINGS.testUrl,


            interval:
            SETTINGS.interval


        });


    }





    /****************************************
     * 没有新增组
     ****************************************/

    if(!newGroups.length){

        return config;

    }





    /****************************************
     * 合并代理组
     ****************************************/

    config["proxy-groups"] = [

        ...newGroups,

        ...oldGroups

    ];




    const addNames =
        newGroups.map(
            g => g.name
        );





    /****************************************
     * 自动寻找主入口 select
     ****************************************/


    const entryGroups =

        config["proxy-groups"]
            .filter(group => {


                if(
                    group.type !== "select"
                ){

                    return false;

                }



                if(
                    !group.proxies ||
                    group.proxies.length < 5
                ){

                    return false;

                }



                if(
                    /自动|测速|故障|容灾/i
                        .test(group.name)
                ){

                    return false;

                }



                return true;


            });





    /****************************************
     * 注入入口组
     ****************************************/

    entryGroups.forEach(group => {


        group.proxies.unshift(

            ...addNames.filter(name =>

                !group.proxies.includes(name)

            )

        );


    });





    return config;

}