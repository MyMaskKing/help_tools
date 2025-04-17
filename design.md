我要做一个wps的python脚本

官方文档：https://365.kdocs.cn/l/cuUFLE0Ufojw   文件形式（官方文档.md）

工作对象：数据表
查询字段名：今天要做什么事，当前数据的链接
查询调节：日期=today,任务标识=1，完成状态=false

你只能通过官方文档生成代码，然后把上面查询到的结果给format成一个html文本，然后发送http的post请求到https://mail.163.com/


