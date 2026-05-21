\ Model WindowBasedModel
\ LP format - for model browsing. Use MPS format to capture full model detail.
\ Signature: 0x166dc5ad425e9aec
Minimize
  29.0898 x_169_0 + 41.5158 x_169_1 + 29.0898 x_169_2 + 41.5158 x_169_3
   + 179.5158 x_169_4 + 112.7106 x_169_5 + 111.7962 x_169_6
   + 44.991 x_169_7 + 111.7962 x_169_8 + 44.991 x_169_9 + 111.7962 x_169_10
   + 44.991 x_169_11 + 29.0898 x_169_12 + 41.5158 x_169_13
   + 53.0418 x_169_14 + 25.0218 x_169_15 + 24.2844 x_169_16
   + 84.8802 x_169_17 + 36.8166 x_169_18 + 70.6056 x_169_20 + 5000 x_169_22
   + 29.0898 x_430_0 + 41.5158 x_430_1 + 29.0898 x_430_2 + 41.5158 x_430_3
   + 179.5158 x_430_4 + 112.7106 x_430_5 + 111.7962 x_430_6
   + 44.991 x_430_7 + 111.7962 x_430_8 + 44.991 x_430_9 + 111.7962 x_430_10
   + 44.991 x_430_11 + 29.0898 x_430_12 + 41.5158 x_430_13
   + 53.0418 x_430_14 + 25.0218 x_430_15 + 24.2844 x_430_16
   + 84.8802 x_430_17 + 36.8166 x_430_18 + 70.6056 x_430_20 + 5000 x_430_22
   + 3000 alpha_0 + 3000 alpha_1 + 3000 alpha_2 + 3000 alpha_3
   + 3000 alpha_4 + 3000 alpha_5 + 3000 alpha_6 + 3000 alpha_9
   + 2500 beta_169 + 2500 beta_430
Subject To
 Hard_Break_Constraint_169: beta_169 = 0
 Hard_Break_Constraint_430: beta_430 = 0
 StartArc_169: x_169_14 + x_169_15 + x_169_16 + x_169_17 + x_169_18 = 1
 StartArc_430: x_430_21 + x_430_22 = 1
 EndArc_169: x_169_0 + x_169_2 + x_169_4 + x_169_6 + x_169_8 + x_169_10
   + x_169_12 + x_169_17 + x_169_19 = 1
 EndArc_430: x_430_1 + x_430_3 + x_430_5 + x_430_7 + x_430_9 + x_430_11
   + x_430_13 + x_430_20 + x_430_22 = 1
 FlowBalance_169_0: x_169_0 + x_169_1 - x_169_14 = 0
 FlowBalance_169_1: x_169_2 + x_169_3 = 0
 FlowBalance_169_2: x_169_4 + x_169_5 = 0
 FlowBalance_169_3: x_169_6 + x_169_7 = 0
 FlowBalance_169_4: x_169_8 + x_169_9 - x_169_15 = 0
 FlowBalance_169_5: x_169_10 + x_169_11 = 0
 FlowBalance_169_6: x_169_12 + x_169_13 - x_169_16 = 0
 FlowBalance_169_9: - x_169_18 + x_169_19 + x_169_20 - x_169_21 = 0
 FlowBalance_430_0: x_430_0 + x_430_1 - x_430_14 = 0
 FlowBalance_430_1: x_430_2 + x_430_3 = 0
 FlowBalance_430_2: x_430_4 + x_430_5 = 0
 FlowBalance_430_3: x_430_6 + x_430_7 = 0
 FlowBalance_430_4: x_430_8 + x_430_9 - x_430_15 = 0
 FlowBalance_430_5: x_430_10 + x_430_11 = 0
 FlowBalance_430_6: x_430_12 + x_430_13 - x_430_16 = 0
 FlowBalance_430_9: - x_430_18 + x_430_19 + x_430_20 - x_430_21 = 0
 ProhibitedStartArc_169: x_169_21 = 0
 ProhibitedStartArc_169: x_169_22 = 0
 ProhibitedStartArc_430: x_430_14 = 0
 ProhibitedStartArc_430: x_430_15 = 0
 ProhibitedStartArc_430: x_430_16 = 0
 ProhibitedStartArc_430: x_430_17 = 0
 ProhibitedStartArc_430: x_430_18 = 0
 ProhibitedTerminationArc_169: x_169_1 = 0
 ProhibitedTerminationArc_169: x_169_3 = 0
 ProhibitedTerminationArc_169: x_169_5 = 0
 ProhibitedTerminationArc_169: x_169_7 = 0
 ProhibitedTerminationArc_169: x_169_9 = 0
 ProhibitedTerminationArc_169: x_169_11 = 0
 ProhibitedTerminationArc_169: x_169_13 = 0
 ProhibitedTerminationArc_169: x_169_20 = 0
 ProhibitedTerminationArc_169: x_169_22 = 0
 ProhibitedTerminationArc_430: x_430_0 = 0
 ProhibitedTerminationArc_430: x_430_2 = 0
 ProhibitedTerminationArc_430: x_430_4 = 0
 ProhibitedTerminationArc_430: x_430_6 = 0
 ProhibitedTerminationArc_430: x_430_8 = 0
 ProhibitedTerminationArc_430: x_430_10 = 0
 ProhibitedTerminationArc_430: x_430_12 = 0
 ProhibitedTerminationArc_430: x_430_17 = 0
 ProhibitedTerminationArc_430: x_430_19 = 0
 Break_30_169: x_169_14 + x_169_15 + x_169_16 + x_169_18 + beta_169
   - y_169_30 >= 0
 Break_30_430: x_430_14 + x_430_15 + x_430_16 + x_430_18 + beta_430
   - y_430_30 >= 0
 Break_45_169: beta_169 - y_169_45 >= 0
 Break_45_430: beta_430 - y_430_45 >= 0
 Assign_Duty_Length169: y_169_0 + y_169_30 + y_169_45 = 1
 Assign_Duty_Length430: y_430_0 + y_430_30 + y_430_45 = 1
 Cover_0: x_169_14 + x_430_14 + alpha_0 >= 1
 Cover_1: alpha_1 >= 1
 Cover_2: alpha_2 >= 1
 Cover_3: alpha_3 >= 1
 Cover_4: x_169_15 + x_430_15 + alpha_4 >= 1
 Cover_5: alpha_5 >= 1
 Cover_6: x_169_16 + x_430_16 + alpha_6 >= 1
 Cover_9: x_169_18 + x_169_21 + x_430_18 + x_430_21 + alpha_9 >= 1
 MaxDur_End_169: 10080 x_169_0 + 10080 x_169_2 + 10080 x_169_4
   + 10080 x_169_6 + 10080 x_169_8 + 10080 x_169_10 + 10080 x_169_12
   + 10080 x_169_19 - 360 y_169_0 - 480 y_169_30 - 720 y_169_45 <= 9788
 MaxDur_Flex_430: 10080 x_430_1 + 10080 x_430_3 + 10080 x_430_5
   + 10080 x_430_7 + 10080 x_430_9 + 10080 x_430_11 + 10080 x_430_13
   + 10080 x_430_20 - 10035 x_430_21 - 360 y_430_0 - 480 y_430_30
   - 720 y_430_45 <= 0
Bounds
Binaries
 x_169_0 x_169_1 x_169_2 x_169_3 x_169_4 x_169_5 x_169_6 x_169_7 x_169_8
 x_169_9 x_169_10 x_169_11 x_169_12 x_169_13 x_169_14 x_169_15 x_169_16
 x_169_17 x_169_18 x_169_19 x_169_20 x_169_21 x_169_22 x_430_0 x_430_1
 x_430_2 x_430_3 x_430_4 x_430_5 x_430_6 x_430_7 x_430_8 x_430_9 x_430_10
 x_430_11 x_430_12 x_430_13 x_430_14 x_430_15 x_430_16 x_430_17 x_430_18
 x_430_19 x_430_20 x_430_21 x_430_22 alpha_0 alpha_1 alpha_2 alpha_3
 alpha_4 alpha_5 alpha_6 alpha_9 beta_169 beta_430 y_169_0 y_169_30
 y_169_45 y_430_0 y_430_30 y_430_45
End
