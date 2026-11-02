# 刷怪塔与农场（Java）

敌对刷怪、塔型、作物动物、防刷、版本坑；以及 **交易厅**、**刷怪笼** 后勤篇。  
目标：**Java 26.3**。

## 已写

| 文档 | 说明 |
|------|------|
| [mob-spawning-basics.md](mob-spawning-basics.md) | 自然刷怪入门 |
| [tower-types.md](tower-types.md) | 水冲/坠落/岩浆营火/爬行者——原理与约束 |
| [crop-animal-farms.md](crop-animal-farms.md) | 作物、甘蔗/竹子、动物 |
| [spawn-proofing.md](spawn-proofing.md) | 防刷与城市规划 |
| [version-pitfalls.md](version-pitfalls.md) | 版本坑 |
| [ai-layout-notes.md](ai-layout-notes.md) | 建筑 AI 布局约束 |
| [trading-hall.md](trading-hall.md) | **村民交易厅**：工作站、床、消毒、布局量级 |
| [spawner-farms.md](spawner-farms.md) | **刷怪笼**农场；传送门金/猪人摘要 |

## 建议阅读顺序

1. `mob-spawning-basics` → 自然塔 `tower-types`  
2. 后勤：`trading-hall`、`spawner-farms`  
3. 城建：`spawn-proofing`  
4. AI：`ai-layout-notes`

## 待写

- [ ] `portal-farms-detail.md` — 传送门金阵列工程向加深  
- [ ] `blaze-spawner.md` — 烈焰人笼专篇  
- [ ] `villager-breeder.md` — 繁殖厅与交易厅分流详图  
- [ ] 创造测试清单打印版  

## 和建筑 AI 的关系

外壳可学；交易隔间与笼房用标签预留空洞 + 模板。刷怪笼不能凭空生成，只能包壳现有结构。
