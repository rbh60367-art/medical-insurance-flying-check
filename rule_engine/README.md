# 代码化规则库

本目录实现医保飞检可执行规则。

规则库不作为普通 RAG 使用。它必须：

- 结构化入库；
- 绑定规则执行器；
- 绑定 SQL 模板；
- 支持金标准案例测试；
- 支持版本和审计。

一期优先实现：

- `GenderLimitRule`
- `AgeLimitRule`
- `DuplicateChargeRule`
